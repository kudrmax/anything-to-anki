from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import CandidateNotPolishedError, PhraseNotFoundError

if TYPE_CHECKING:
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock


class RevertPhrasePolishUseCase:
    """Switches a card between AI's polished phrase and the phrase from the source."""

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        enrichment_reset: PhraseEnrichmentReset,
        lock: SourceOperationLock,
    ) -> None:
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._enrichment_reset = enrichment_reset
        self._lock = lock

    def execute(self, phrase_id: int, reverted: bool) -> None:
        occ = self._occurrences.get(phrase_id)
        word = self._candidate_repo.get_by_id(occ.candidate_id) if occ is not None else None
        if occ is None or word is None:
            raise PhraseNotFoundError(phrase_id)
        ensure_source_free(self._lock, word.source_id)
        polished = occ.polished_phrase
        if polished is None or polished.text == occ.source_phrase.text:
            raise CandidateNotPolishedError(phrase_id)
        if occ.polish_reverted != reverted:
            self._occurrences.write_text(
                phrase_id, occ.source_phrase, occ.phrase_position,
                polished=polished, polish_reverted=reverted, bump_revision=True,
            )
            self._enrichment_reset.reset_phrase(phrase_id)
