from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import (
    InvalidPhraseError,
    PhraseNotFoundError,
    SourceHasNoDocumentError,
)
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock

logger = logging.getLogger(__name__)

TARGET_OUTSIDE = "Target must be inside the phrase"


class SetPhraseBoundaryUseCase:
    """The user selects the phrase of a card anew on the source screen.

    The phrase becomes that piece of the document, cut by the user; the target stays the
    same place in the document and must be inside the new piece. A phrase that had no place
    (an example) finds its target by the word's dictionary form; either way the phrase's key
    is where its target starts (it moves only for a phrase that had no place, as the target
    of the others stays where it was). Nothing else is recomputed.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        document_repo: DocumentRepository,
        phrase_reader: PhraseReader,
        lock: SourceOperationLock,
        stamper: SectionStamper,
    ) -> None:
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._document_repo = document_repo
        self._phrase_reader = phrase_reader
        self._lock = lock
        self._stamper = stamper

    def execute(self, occurrence_id: int, selection: SelectionDTO) -> str:
        occ = self._occurrences.get(occurrence_id)
        word = self._candidate_repo.get_by_id(occ.candidate_id) if occ is not None else None
        if occ is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        document = self._document_repo.get(word.source_id)
        if document is None:
            raise SourceHasNoDocumentError(word.source_id)
        layout = DocumentLayout(document)
        position = layout.selected(selection.start, selection.end)
        text = layout.fragment(position)
        if occ.phrase_position is None:
            phrase = self._phrase_reader.read_for(text, word.lemma)
        else:
            phrase = self._phrase_reader.read(
                text, self._target_in(layout, occ, layout.span(position)),
            )
        self._occurrences.write_text(
            occurrence_id, phrase, position,
            earned_section=self._stamper.earned(phrase, word), edited_by_user=True,
        )
        if occ.key is None or occ.phrase_position is None:
            self._occurrences.set_key(occurrence_id, layout.target_key(position, phrase))
        logger.info("Set phrase %d: %r", occurrence_id, text)
        return text

    @staticmethod
    def _target_in(
        layout: DocumentLayout, occ: Occurrence, piece: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """Where the target stands in the document, as characters of the new piece."""
        assert occ.phrase_position is not None
        old_start, _ = layout.span(occ.phrase_position)
        source = occ.source_phrase
        spans = [
            (old_start + source.words[i].start, old_start + source.words[i].end)
            for i in source.target
        ]
        if any(start < piece[0] or end > piece[1] for start, end in spans):
            raise InvalidPhraseError(TARGET_OUTSIDE)
        return [(start - piece[0], end - piece[0]) for start, end in spans]
