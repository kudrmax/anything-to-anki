from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError, SourceHasNoDocumentError
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class SetPhraseBoundaryUseCase:
    """The user selects the phrase of a card anew on the source screen.

    The phrase becomes that piece of the document; nothing else is recomputed.
    """

    def __init__(
        self, candidate_repo: CandidateRepository, document_repo: DocumentRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._document_repo = document_repo

    def execute(self, candidate_id: int, selection: SelectionDTO) -> str:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        document = self._document_repo.get(candidate.source_id)
        if document is None:
            raise SourceHasNoDocumentError(candidate.source_id)
        layout = DocumentLayout(document)
        position = layout.selected(selection.start, selection.end)
        phrase = layout.fragment(position)
        self._candidate_repo.update_phrase(candidate_id, phrase, position)
        logger.info("Set phrase of candidate %d: %r", candidate_id, phrase)
        return phrase
