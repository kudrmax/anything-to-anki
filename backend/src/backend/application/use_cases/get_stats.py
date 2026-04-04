from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.stats_dtos import StatsDTO
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository


class GetStatsUseCase:
    """Returns aggregate statistics: total LEARN candidates and known word count."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo

    def execute(self) -> StatsDTO:
        learn_count = self._candidate_repo.count_by_status(CandidateStatus.LEARN)
        known_word_count = self._known_word_repo.count()
        return StatsDTO(learn_count=learn_count, known_word_count=known_word_count)
