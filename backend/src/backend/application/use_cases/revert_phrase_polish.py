from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError, CandidateNotPolishedError

if TYPE_CHECKING:
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.domain.ports.candidate_repository import CandidateRepository


class RevertPhrasePolishUseCase:
    """Switches a card between AI's polished phrase and the phrase from the source."""

    def __init__(
        self, candidate_repo: CandidateRepository, enrichment_reset: PhraseEnrichmentReset,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._enrichment_reset = enrichment_reset

    def execute(self, candidate_id: int, reverted: bool) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        if not candidate.is_polished:
            raise CandidateNotPolishedError(candidate_id)
        if candidate.polish_reverted != reverted:
            self._candidate_repo.set_polish_reverted(candidate.id, reverted)
            self._enrichment_reset.reset(candidate.id)
