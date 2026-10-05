from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError

if TYPE_CHECKING:
    from backend.application.utils.card_picture_placer import CardPicturePlacer
    from backend.domain.ports.candidate_repository import CandidateRepository

logger = logging.getLogger(__name__)


class PasteTargetImageUseCase:
    """Puts a picture the user brought themselves (e.g. from the clipboard) on the card."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        picture_placer: CardPicturePlacer,
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
