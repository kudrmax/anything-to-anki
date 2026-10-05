from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.exceptions import (
    CandidateNotFoundError,
    TargetImageNotSupportedError,
    UnknownImageUrlError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_picture_encoder import CardPictureEncoder
    from backend.domain.ports.file_downloader import FileDownloader
    from backend.domain.ports.target_image_source import TargetImageSource

logger = logging.getLogger(__name__)

URL_DIGEST_LENGTH = 10
DOWNLOAD_SUFFIX = ".download"


class ApplyTargetImageUseCase:
    """Puts a picked picture on the card in place of its current picture.

    The picture is shrunk by the same encoder as video frames, so a card
    carries the same compact WebP whichever way it got its picture. The file
    name carries a digest of the URL, so picking another picture changes the
    name and nothing keeps showing a cached old one.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        media_repo: CandidateMediaRepository,
        image_sources: Sequence[TargetImageSource],
        file_downloader: FileDownloader,
        picture_encoder: CardPictureEncoder,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._media_repo = media_repo
        self._image_sources = image_sources
        self._file_downloader = file_downloader
        self._picture_encoder = picture_encoder
        self._media_root = media_root

    def execute(self, candidate_id: int, url: str) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        if not candidate.can_have_target_image:
            raise TargetImageNotSupportedError(candidate_id)
        if not any(source.owns(url) for source in self._image_sources):
            raise UnknownImageUrlError(url)

        out_dir = os.path.join(self._media_root, str(candidate.source_id))
        os.makedirs(out_dir, exist_ok=True)
        image_path = os.path.join(out_dir, _image_file_name(candidate_id, url))
        self._download_and_encode(url, image_path)

        previous = candidate.media
        _remove_replaced_picture(previous, image_path)
        self._media_repo.upsert(_with_picture(candidate_id, previous, image_path))
        logger.info("apply_target_image: candidate %d got %s", candidate_id, url)

    def _download_and_encode(self, url: str, image_path: str) -> None:
        downloaded_path = f"{image_path}{DOWNLOAD_SUFFIX}"
        try:
            self._file_downloader.download(url, downloaded_path)
            with open(downloaded_path, "rb") as downloaded:
                self._picture_encoder.encode(downloaded.read(), image_path)
        finally:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)


def _image_file_name(candidate_id: int, url: str) -> str:
    digest = hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:URL_DIGEST_LENGTH]
    return f"{candidate_id}_screenshot.{digest}.webp"


def _remove_replaced_picture(previous: CandidateMedia | None, new_path: str) -> None:
    old_path = previous.screenshot_path if previous else None
    if old_path and old_path != new_path and os.path.exists(old_path):
        os.remove(old_path)


def _with_picture(
    candidate_id: int, previous: CandidateMedia | None, image_path: str,
) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=candidate_id,
        screenshot_path=image_path,
        audio_path=previous.audio_path if previous else None,
        start_ms=previous.start_ms if previous else None,
        end_ms=previous.end_ms if previous else None,
        generated_at=datetime.now(tz=UTC),
    )
