from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_meaning_image_repository import (
        CandidateMeaningImageRepository,
    )
    from backend.domain.ports.card_picture_encoder import CardPictureEncoder

PICTURE_DIGEST_LENGTH = 10


class MeaningImagePlacer:
    """Puts a picture on the card as its meaning image, in place of the previous one.

    The video frame of the card is left alone. The picture is shrunk by the
    same encoder as video frames, so a card carries the same compact WebP
    whichever way it got its picture. The file name carries a digest of where
    the picture came from, so another picture changes the name and nothing
    keeps showing a cached old one.
    """

    def __init__(
        self,
        image_repo: CandidateMeaningImageRepository,
        picture_encoder: CardPictureEncoder,
        media_root: str,
    ) -> None:
        self._image_repo = image_repo
        self._picture_encoder = picture_encoder
        self._media_root = media_root

    def picture_dir(self, candidate: StoredCandidate) -> str:
        out_dir = os.path.join(self._media_root, str(candidate.source_id))
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def place(self, candidate: StoredCandidate, picture: bytes, origin: bytes) -> None:
        """Raises OSError when the bytes are not a picture; the card stays as it was."""
        assert candidate.id is not None
        file_name = _image_file_name(candidate.id, origin)
        image_path = os.path.join(self.picture_dir(candidate), file_name)
        self._picture_encoder.encode(picture, image_path)

        _remove_replaced_picture(candidate.meaning_image, image_path)
        self._image_repo.upsert(
            CandidateMeaningImage(candidate_id=candidate.id, image_path=image_path),
        )


def _image_file_name(candidate_id: int, origin: bytes) -> str:
    digest = hashlib.sha1(origin, usedforsecurity=False).hexdigest()[:PICTURE_DIGEST_LENGTH]
    return f"{candidate_id}_meaning.{digest}.webp"


def _remove_replaced_picture(previous: CandidateMeaningImage | None, new_path: str) -> None:
    old_path = previous.image_path if previous else None
    if old_path and old_path != new_path and os.path.exists(old_path):
        os.remove(old_path)
