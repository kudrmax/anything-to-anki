from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    CandidateNotFoundError,
    InvalidPhraseError,
    SourceHasNoDocumentError,
)
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

TARGET_OUTSIDE = "Target must be inside the phrase"


class SetPhraseBoundaryUseCase:
    """The user selects the phrase of a card anew on the source screen.

    The phrase becomes that piece of the document; the target stays the same place in the
    document and must be inside the new piece. Nothing else is recomputed.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        document_repo: DocumentRepository,
        phrase_reader: PhraseReader,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._document_repo = document_repo
        self._phrase_reader = phrase_reader

    def execute(self, candidate_id: int, selection: SelectionDTO) -> str:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        document = self._document_repo.get(candidate.source_id)
        if document is None:
            raise SourceHasNoDocumentError(candidate.source_id)
        layout = DocumentLayout(document)
        position = layout.selected(selection.start, selection.end)
        text = layout.fragment(position)
        if candidate.phrase_position is None:
            phrase = self._phrase_reader.read_for(text, candidate.lemma)
        else:
            phrase = self._phrase_reader.read(
                text, self._target_in(layout, candidate, layout.span(position)),
            )
        self._candidate_repo.set_source_phrase(candidate.id, phrase, position)
        logger.info("Set phrase of candidate %d: %r", candidate_id, text)
        return text

    @staticmethod
    def _target_in(
        layout: DocumentLayout, candidate: StoredCandidate, piece: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """Where the target stands in the document, as characters of the new piece."""
        assert candidate.phrase_position is not None
        old_start, _ = layout.span(candidate.phrase_position)
        source = candidate.source_phrase
        spans = [
            (old_start + source.words[i].start, old_start + source.words[i].end)
            for i in source.target
        ]
        if any(start < piece[0] or end > piece[1] for start, end in spans):
            raise InvalidPhraseError(TARGET_OUTSIDE)
        return [(start - piece[0], end - piece[0]) for start, end in spans]
