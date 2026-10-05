from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    CandidateNotFoundError,
    UnknownImageUrlError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.card_picture_placer import CardPicturePlacer
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.file_downloader import FileDownloader
    from backend.domain.ports.target_image_source import TargetImageSource

logger = logging.getLogger(__name__)

DOWNLOAD_SUFFIX = ".download"


class ApplyTargetImageUseCase:
    """Puts a picture picked from the search results on the card."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        image_sources: Sequence[TargetImageSource],
        file_downloader: FileDownloader,
        picture_placer: CardPicturePlacer,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._image_sources = image_sources
        self._file_downloader = file_downloader
        self._picture_placer = picture_placer

    def execute(self, candidate_id: int, url: str) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        if not any(source.owns(url) for source in self._image_sources):
            raise UnknownImageUrlError(url)

        downloaded_path = os.path.join(
            self._picture_placer.picture_dir(candidate), f"{candidate_id}{DOWNLOAD_SUFFIX}",
        )
        try:
            self._file_downloader.download(url, downloaded_path)
            with open(downloaded_path, "rb") as downloaded:
                picture = downloaded.read()
        finally:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)

        self._picture_placer.place(candidate, picture, origin=url.encode())
        logger.info("apply_target_image: candidate %d got %s", candidate_id, url)
