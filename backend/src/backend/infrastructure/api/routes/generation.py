from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


@router.post("/sources/{source_id}/meanings/generate", status_code=202)
def enqueue_meaning_generation(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue jobs for meaning generation, batched by 15.
    Order of enqueue follows sort param ('relevance' or 'chronological')."""
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    try:
        sort_order = CandidateSortOrder(sort)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort: {sort}. Use 'relevance' or 'chronological'.",
        ) from e

    use_case = container.enqueue_meaning_generation_use_case(session)
    batches = use_case.execute(source_id, sort_order=sort_order)
    session.commit()

    total = sum(len(b) for b in batches)
    return {"enqueued": total, "batches": len(batches)}


@router.post("/sources/{source_id}/meanings/cancel")
def cancel_meaning_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued AND running meaning generation jobs."""
    job_repo = container.job_repository(session)
    cancelled = job_repo.delete_by_source_and_type(source_id, JobType.MEANING)
    session.commit()
    return {"cancelled": cancelled}


@router.post("/sources/{source_id}/meanings/retry-failed", status_code=202)
def retry_failed_meanings(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue failed meaning generation jobs, batched by 15."""
    job_repo = container.job_repository(session)
    failed_jobs = job_repo.delete_failed_by_source_and_type(source_id, JobType.MEANING)
    if not failed_jobs:
        logger.info(
            "generation.retry_failed: no failed candidates (source_id=%d)", source_id,
        )
        return {"enqueued": 0, "batches": 0}

    now = datetime.now(tz=UTC)
    new_jobs = [
        Job(
            id=None,
            job_type=JobType.MEANING,
            candidate_id=j.candidate_id,
            source_id=source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=now,
            started_at=None,
        )
        for j in failed_jobs
    ]
    job_repo.create_bulk(new_jobs)
    session.commit()

    batch_size = 15
    batches_count = (len(new_jobs) + batch_size - 1) // batch_size
    logger.info(
        "generation.retry_failed: re-enqueued "
        "(source_id=%d, total=%d, batches=%d)",
        source_id, len(new_jobs), batches_count,
    )
    return {"enqueued": len(new_jobs), "batches": batches_count}
