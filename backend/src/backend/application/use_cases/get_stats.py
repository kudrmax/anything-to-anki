from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.stats_dtos import StatsDTO
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.application.utils.export_queue import ExportQueue
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository


class GetStatsUseCase:
    """Aggregate stats: LEARN candidates, cards awaiting export, active jobs, known words."""

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
        learn_count = self._candidate_repo.count_by_status(WordStatus.LEARN)
        export_pending_count = len(self._export_queue.for_all().pending)
        queue_active_count = self._count_active_jobs()
        candidate_count = self._candidate_repo.count_all()
        known_word_count = self._vocabulary.known_count()
        return StatsDTO(
            learn_count=learn_count,
            export_pending_count=export_pending_count,
            queue_active_count=queue_active_count,
            candidate_count=candidate_count,
            known_word_count=known_word_count,
        )

    def _count_active_jobs(self) -> int:
        active = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
        return sum(
            by_status.get(status, 0)
            for by_status in self._job_repo.get_queue_summary().values()
            for status in active
        )
