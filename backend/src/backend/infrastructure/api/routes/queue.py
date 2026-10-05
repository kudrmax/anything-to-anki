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
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

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
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueSnapshotDTO:
    use_case = container.get_queue_snapshot_use_case(session)
    return use_case.execute(source_id=source_id, queued_limit=queued_limit)


@router.post("/cancel")
def cancel(
    body: QueueActionRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueActionResultDTO:
    affected = container.manage_queue_use_case(session).cancel(_selection(body))
    session.commit()
    return QueueActionResultDTO(affected=affected)


@router.post("/retry")
def retry(
    body: QueueActionRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueActionResultDTO:
    affected = container.manage_queue_use_case(session).retry(_selection(body))
    session.commit()
    return QueueActionResultDTO(affected=affected)


@router.post("/dismiss")
def dismiss(
    body: QueueActionRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueActionResultDTO:
    affected = container.manage_queue_use_case(session).dismiss(_selection(body))
    session.commit()
    return QueueActionResultDTO(affected=affected)
