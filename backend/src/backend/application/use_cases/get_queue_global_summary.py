from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import JobTypeSummaryDTO, QueueGlobalSummaryDTO

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository


class GetQueueGlobalSummaryUseCase:
    """Aggregate queued/running/failed counts for all job types."""

    def __init__(self, job_repo: JobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, source_id: int | None = None) -> QueueGlobalSummaryDTO:
        raw = self._job_repo.get_queue_summary(source_id=source_id)
        zero = JobTypeSummaryDTO(queued=0, running=0, failed=0)

        def _summary(key: str) -> JobTypeSummaryDTO:
            data = raw.get(key)
            if data is None:
                return zero
            return JobTypeSummaryDTO(
                queued=data.get("queued", 0),
                running=data.get("running", 0),
                failed=data.get("failed", 0),
            )

        return QueueGlobalSummaryDTO(
            meaning=_summary("meaning"),
            media=_summary("media"),
            pronunciation=_summary("pronunciation"),
            video_download=_summary("video_download"),
        )
