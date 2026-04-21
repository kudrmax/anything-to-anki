from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.queue_dtos import (  # noqa: TC001
    CancelRequestDTO,
    QueueFailedDTO,
    QueueGlobalSummaryDTO,
    QueueOrderDTO,
    RetryRequestDTO,
)
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.get("/global-summary")
def get_global_summary(
    source_id: int | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueGlobalSummaryDTO:
    use_case = container.get_queue_global_summary_use_case(session)
    return use_case.execute(source_id=source_id)


@router.get("/order")
async def get_queue_order(
    source_id: int | None = None,
    limit: int = 50,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueOrderDTO:
    use_case = await container.get_queue_order_use_case(session)
    return await use_case.execute(source_id=source_id, limit=limit)


@router.get("/failed")
def get_failed(
    source_id: int | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueFailedDTO:
    use_case = container.get_queue_failed_use_case(session)
    return use_case.execute(source_id=source_id)


@router.post("/retry")
def retry_failed(
    body: RetryRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    use_case = container.retry_queue_use_case(session)
    count = use_case.execute(
        job_type=body.job_type,
        source_id=body.source_id,
        error_text=body.error_text,
    )
    session.commit()
    return {"retried": count}


@router.post("/cancel")
async def cancel_queued(
    body: CancelRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    use_case = await container.cancel_queue_use_case(session)
    count = await use_case.execute(
        job_type=body.job_type,
        source_id=body.source_id,
        job_id=body.job_id,
    )
    session.commit()
    return {"cancelled": count}
