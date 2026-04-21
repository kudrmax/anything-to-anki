from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import QueueJobDTO, QueueOrderDTO

if TYPE_CHECKING:
    from backend.domain.ports.queue_inspector import QueueInspectorPort
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.queued_job_info import QueuedJobInfo


class GetQueueOrderUseCase:
    """Return ordered running + queued jobs with source titles."""

    def __init__(
        self,
        inspector: QueueInspectorPort,
        source_repo: SourceRepository,
    ) -> None:
        self._inspector = inspector
        self._source_repo = source_repo

    async def execute(
        self,
        source_id: int | None = None,
        limit: int = 50,
    ) -> QueueOrderDTO:
        running_jobs = await self._inspector.get_running_jobs(source_id=source_id)
        queued_jobs = await self._inspector.get_queued_jobs(source_id=source_id, limit=limit)
        total_queued = await self._inspector.get_total_queued()

        all_source_ids = list({j.source_id for j in running_jobs + queued_jobs})
        title_map = self._source_repo.get_title_map(all_source_ids) if all_source_ids else {}

        def _to_dto(job: QueuedJobInfo, status: str) -> QueueJobDTO:
            return QueueJobDTO(
                job_id=job.job_id,
                job_type=job.job_type,
                source_id=job.source_id,
                source_title=title_map.get(job.source_id, ""),
                status=status,
                position=job.position,
                substage=None,
            )

        return QueueOrderDTO(
            running=[_to_dto(j, "running") for j in running_jobs],
            queued=[_to_dto(j, "queued") for j in queued_jobs],
            total_queued=total_queued,
        )
