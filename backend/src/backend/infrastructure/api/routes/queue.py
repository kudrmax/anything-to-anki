from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.queue_dtos import (  # noqa: TC001
    QueueActionRequestDTO,
    QueueActionResultDTO,
    QueueSnapshotDTO,
)
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.get_queue_snapshot import GetQueueSnapshotUseCase
    from backend.application.use_cases.manage_queue import ManageQueueUseCase

router = APIRouter(prefix="/api/queue", tags=["queue"])


def _selection(body: QueueActionRequestDTO) -> JobSelection:
    try:
        job_type = JobType(body.job_type) if body.job_type is not None else None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unknown job type: {body.job_type}") from e
    return JobSelection(
        job_type=job_type, source_id=body.source_id, job_id=body.job_id, error=body.error_text,
    )


@router.get("")
def get_queue(
    source_id: int | None = None,
    queued_limit: int = 50,
    snapshot: GetQueueSnapshotUseCase = Depends(  # noqa: B008
        use_case(Container.get_queue_snapshot_use_case),  # noqa: B008
    ),
) -> QueueSnapshotDTO:
    return snapshot.execute(source_id=source_id, queued_limit=queued_limit)


@router.post("/cancel")
def cancel(
    body: QueueActionRequestDTO,
    queue: ManageQueueUseCase = Depends(use_case(Container.manage_queue_use_case)),  # noqa: B008
) -> QueueActionResultDTO:
    affected = queue.cancel(_selection(body))
    return QueueActionResultDTO(affected=affected)


@router.post("/retry")
def retry(
    body: QueueActionRequestDTO,
    queue: ManageQueueUseCase = Depends(use_case(Container.manage_queue_use_case)),  # noqa: B008
) -> QueueActionResultDTO:
    affected = queue.retry(_selection(body))
    return QueueActionResultDTO(affected=affected)


@router.post("/dismiss")
def dismiss(
    body: QueueActionRequestDTO,
    queue: ManageQueueUseCase = Depends(use_case(Container.manage_queue_use_case)),  # noqa: B008
) -> QueueActionResultDTO:
    affected = queue.dismiss(_selection(body))
    return QueueActionResultDTO(affected=affected)
