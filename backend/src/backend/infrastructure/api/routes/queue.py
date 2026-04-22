from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.queue_dtos import (  # noqa: TC001
    CancelRequestDTO,
    QueueFailedDTO,
    QueueGlobalSummaryDTO,
    QueueOrderDTO,
    RetryRequestDTO,
)
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])

# Map frontend job_type strings to JobType enum
_JOB_TYPE_MAP: dict[str, JobType] = {
    "meaning": JobType.MEANING,
    "media": JobType.MEDIA,
    "pronunciation": JobType.PRONUNCIATION,
    "video_download": JobType.VIDEO_DOWNLOAD,
}


# ── READ endpoints ──────────────────────────────────────────────────


@router.get("/global-summary")
def get_global_summary(
    source_id: int | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueGlobalSummaryDTO:
    use_case = container.get_queue_global_summary_use_case(session)
    return use_case.execute(source_id=source_id)


@router.get("/order")
def get_queue_order(
    source_id: int | None = None,
    limit: int = 50,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueOrderDTO:
    use_case = container.get_queue_order_use_case(session)
    return use_case.execute(source_id=source_id, limit=limit)


@router.get("/failed")
def get_failed(
    source_id: int | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QueueFailedDTO:
    use_case = container.get_queue_failed_use_case(session)
    return use_case.execute(source_id=source_id)


# ── ACTION endpoints ────────────────────────────────────────────────


@router.post("/cancel")
def cancel_queued(
    body: CancelRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued+running jobs via JobRepository."""
    job_type = _JOB_TYPE_MAP.get(body.job_type)
    if job_type is None:
        return {"cancelled": 0}

    job_repo = container.job_repository(session)

    if body.job_id is not None:
        # Cancel a single job
        job_repo.delete(body.job_id)
        session.commit()
        return {"cancelled": 1}

    if body.source_id is not None:
        # Cancel all jobs of type for a specific source
        count = job_repo.delete_by_source_and_type(body.source_id, job_type)
        session.commit()
        return {"cancelled": count}

    # Cancel all jobs of type globally
    source_ids = job_repo.get_source_ids_with_active_jobs(job_type)
    total = 0
    for sid in source_ids:
        total += job_repo.delete_by_source_and_type(sid, job_type)
    session.commit()
    return {"cancelled": total}


@router.post("/retry", status_code=202)
def retry_failed(
    body: RetryRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue failed jobs via JobRepository."""
    job_type = _JOB_TYPE_MAP.get(body.job_type)
    if job_type is None:
        return {"retried": 0}

    job_repo = container.job_repository(session)

    # Get failed jobs matching the filter
    failed_groups = job_repo.get_failed_grouped_by_error(
        source_id=body.source_id, job_type=job_type,
    )

    # Filter by error_text if specified
    candidate_ids_set: set[int] = set()
    source_ids_to_retry: set[int] = set()
    for group in failed_groups:
        if body.error_text is not None and group["error"] != body.error_text:
            continue
        candidate_ids_set.update(group["candidate_ids"])
        source_ids_to_retry.update(group["source_ids"])

    if not candidate_ids_set:
        return {"retried": 0}

    # Delete failed jobs and re-create matching ones as QUEUED.
    # When filtering by error_text, delete_failed_by_source_and_type removes ALL
    # failed jobs for the source+type. We must re-insert non-matching ones as FAILED.
    to_retry: list[Job] = []
    to_preserve: list[Job] = []
    for sid in source_ids_to_retry:
        deleted = job_repo.delete_failed_by_source_and_type(sid, job_type)
        for j in deleted:
            if body.error_text is not None and j.candidate_id not in candidate_ids_set:
                to_preserve.append(j)
            else:
                to_retry.append(j)

    if not to_retry:
        # Re-insert preserved jobs if we deleted but found nothing to retry
        if to_preserve:
            preserved_jobs = [
                Job(
                    id=None,
                    job_type=j.job_type,
                    candidate_id=j.candidate_id,
                    source_id=j.source_id,
                    status=j.status,
                    error=j.error,
                    created_at=j.created_at,
                    started_at=j.started_at,
                )
                for j in to_preserve
            ]
            job_repo.create_bulk(preserved_jobs)
            session.commit()
        return {"retried": 0}

    now = datetime.now(tz=UTC)
    new_jobs = [
        Job(
            id=None,
            job_type=job_type,
            candidate_id=j.candidate_id,
            source_id=j.source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=now,
            started_at=None,
        )
        for j in to_retry
    ]
    # Re-insert non-matching failed jobs to preserve them
    if to_preserve:
        preserved_jobs = [
            Job(
                id=None,
                job_type=j.job_type,
                candidate_id=j.candidate_id,
                source_id=j.source_id,
                status=j.status,
                error=j.error,
                created_at=j.created_at,
                started_at=j.started_at,
            )
            for j in to_preserve
        ]
        job_repo.create_bulk(preserved_jobs)
    job_repo.create_bulk(new_jobs)
    session.commit()

    return {"retried": len(new_jobs)}
