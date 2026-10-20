from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.stats_dtos import StatsDTO
from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.application.utils.export_queue import ExportQueue
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository


class GetStatsUseCase:
    """Aggregate stats: words in the export queue (Learn, not in Anki yet), words learning
    in Anki, active jobs, Known words (by the list or the timer, each lemma once)."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        vocabulary: UserVocabulary,
        export_queue: ExportQueue,
        job_repo: JobRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._vocabulary = vocabulary
        self._export_queue = export_queue
        self._job_repo = job_repo

    def execute(self) -> StatsDTO:
        learning_count = self._candidate_repo.count_learning_in_anki()
        export_pending_count = self._export_queue.pending_count()
        queue_active_count = self._count_active_jobs()
        candidate_count = self._candidate_repo.count_all()
        known_word_count = self._vocabulary.known_count()
        return StatsDTO(
            learning_count=learning_count,
            export_pending_count=export_pending_count,
            queue_active_count=queue_active_count,
            candidate_count=candidate_count,
            known_word_count=known_word_count,
            ai_unavailable=self._job_repo.waiting_reason(),
        )

    def _count_active_jobs(self) -> int:
        active = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
        return sum(
            by_status.get(status, 0)
            for by_status in self._job_repo.get_queue_summary().values()
            for status in active
        )
