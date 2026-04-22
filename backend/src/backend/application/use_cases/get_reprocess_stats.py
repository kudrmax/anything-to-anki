from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.source_repository import SourceRepository


@dataclass(frozen=True)
class ReprocessStats:
    learn_count: int
    known_count: int
    skip_count: int
    pending_count: int
    has_active_jobs: bool


class GetReprocessStatsUseCase:
    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
        job_repo: JobRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo
        self._job_repo = job_repo

    def execute(self, source_id: int) -> ReprocessStats:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        candidates = self._candidate_repo.get_by_source(source_id)
        known_pairs = self._known_word_repo.get_all_pairs()

        learn_lost_count = 0
        known_lost_count = 0
        skip_count = 0
        pending_count = 0

        for c in candidates:
            if c.status == CandidateStatus.LEARN:
                if (c.lemma, c.pos) not in known_pairs:
                    learn_lost_count += 1
            elif c.status == CandidateStatus.KNOWN:
                if (c.lemma, c.pos) not in known_pairs:
                    known_lost_count += 1
            elif c.status == CandidateStatus.SKIP:
                skip_count += 1
            elif c.status == CandidateStatus.PENDING:
                pending_count += 1

        has_active = self._job_repo.has_active_jobs_for_source(source_id)

        return ReprocessStats(
            learn_count=learn_lost_count,
            known_count=known_lost_count,
            skip_count=skip_count,
            pending_count=pending_count,
            has_active_jobs=has_active,
        )
