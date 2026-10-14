from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.value_objects.decision_progress import DecisionProgress


class ReviewProgress:
    """How far the user got with a source, by what they know right now. Everything that
    shows or sums progress — a source, its review screen, a collection — takes it from here."""

    def __init__(
        self, candidate_repo: CandidateRepository, candidate_sorter: CandidateSorter,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._candidate_sorter = candidate_sorter

    def of_source(self, source_id: int) -> DecisionProgress:
        candidates = self._candidate_repo.get_by_source(source_id)
        return self._candidate_sorter.arrange(candidates).progress()
