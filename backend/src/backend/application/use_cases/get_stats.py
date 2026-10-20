from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.stats_dtos import AIOutageDTO, StatsDTO
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import AI_JOB_TYPES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from backend.application.utils.export_queue import ExportQueue
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.ai_outage_repository import AIOutageRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository


class GetStatsUseCase:
    """Aggregate stats: words in the export queue (Learn, not in Anki yet), words learning
    in Anki, active jobs, Known words (by the list or the timer, each lemma once), and the
    current outage of the AI."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        vocabulary: UserVocabulary,
        export_queue: ExportQueue,
        job_repo: JobRepository,
        ai_outage_repo: AIOutageRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._vocabulary = vocabulary
        self._export_queue = export_queue
        self._job_repo = job_repo
        self._ai_outage_repo = ai_outage_repo

    def execute(self) -> StatsDTO:
        learning_count = self._candidate_repo.count_learning_in_anki()
        export_pending_count = self._export_queue.pending_count()
        summary = self._job_repo.get_queue_summary()
        queue_active_count = self._count_active(summary.values())
        candidate_count = self._candidate_repo.count_all()
        known_word_count = self._vocabulary.known_count()
        outage = self._ai_outage_repo.get()
        return StatsDTO(
            learning_count=learning_count,
            export_pending_count=export_pending_count,
            queue_active_count=queue_active_count,
            candidate_count=candidate_count,
            known_word_count=known_word_count,
            ai_outage=AIOutageDTO(
                reason=outage.reason,
                since=outage.since,
                vpn_required=outage.vpn_required,
                queue_waits=self._count_active(
                    summary.get(job_type.value, {}) for job_type in AI_JOB_TYPES
                ) > 0,
            ) if outage is not None else None,
        )

    @staticmethod
    def _count_active(summaries: Iterable[Mapping[str, int]]) -> int:
        active = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
        return sum(by_status.get(status, 0) for by_status in summaries for status in active)
