from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import QueueJobDTO, QueueOrderDTO
from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class GetQueueOrderUseCase:
    """Return ordered running + queued jobs with source titles."""

    def __init__(
        self,
        job_repo: JobRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._job_repo = job_repo
        self._source_repo = source_repo

    def execute(
        self,
        source_id: int | None = None,
        limit: int = 50,
    ) -> QueueOrderDTO:
        running = self._job_repo.get_jobs_by_status(
            statuses=[JobStatus.RUNNING], source_id=source_id,
        )
        queued = self._job_repo.get_jobs_by_status(
            statuses=[JobStatus.QUEUED], source_id=source_id, limit=limit,
        )
        # Count total queued separately (may be more than limit)
        all_queued = self._job_repo.get_jobs_by_status(
            statuses=[JobStatus.QUEUED], source_id=source_id,
        )

        all_source_ids = list({j.source_id for j in running + queued})
        title_map = self._source_repo.get_title_map(all_source_ids) if all_source_ids else {}

        def _to_dto(job: Job, status: str, position: int | None = None) -> QueueJobDTO:
            return QueueJobDTO(
                job_id=job.id or 0,
                job_type=job.job_type.value,
                source_id=job.source_id,
                source_title=title_map.get(job.source_id, ""),
                status=status,
                position=position,
                candidate_id=job.candidate_id,
            )

        return QueueOrderDTO(
            running=[_to_dto(j, "running") for j in running],
            queued=[_to_dto(j, "queued", i + 1) for i, j in enumerate(queued)],
            total_queued=len(all_queued),
        )
