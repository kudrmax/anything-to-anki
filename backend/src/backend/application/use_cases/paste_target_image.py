from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError

if TYPE_CHECKING:
    from backend.application.utils.meaning_image_placer import MeaningImagePlacer
    from backend.domain.ports.candidate_repository import CandidateRepository

logger = logging.getLogger(__name__)


class PasteTargetImageUseCase:
    """Puts a picture the user brought (e.g. from the clipboard) on the card as its meaning."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        picture_placer: MeaningImagePlacer,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._picture_placer = picture_placer

    def execute(self, candidate_id: int, picture: bytes) -> None:
        """Raises OSError when the bytes are not a picture."""
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        self._picture_placer.place(candidate, picture, origin=picture)
        logger.info("paste_target_image: candidate %d got %d bytes", candidate_id, len(picture))
