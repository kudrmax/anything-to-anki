from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["media"])


@router.get("/media/{source_id}/{filename}")
async def serve_media_file(
    source_id: int,
    filename: str,
    container: Container = Depends(get_container),  # noqa: B008
) -> FileResponse:
    media_root = container.media_root()
    file_path = os.path.join(media_root, str(source_id), filename)
    if not os.path.exists(file_path):
        await container.lazy_media_reconciler().schedule(source_id, filename)
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)


@router.post("/sources/{source_id}/media/generate", status_code=202)
def enqueue_media_generation(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue jobs for all eligible candidates (those with timecodes but no screenshot).
    Order of enqueue follows sort param ('relevance' or 'chronological')."""
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    try:
        sort_order = CandidateSortOrder(sort)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort: {sort}. Use 'relevance' or 'chronological'.",
        ) from e

    use_case = container.enqueue_media_generation_use_case(session)
    eligible_ids = use_case.execute(source_id, sort_order=sort_order)
    session.commit()

    return {"enqueued": len(eligible_ids)}


@router.post("/sources/{source_id}/media/cancel")
def cancel_media_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued AND running media extraction jobs."""
    job_repo = container.job_repository(session)
    cancelled = job_repo.delete_by_source_and_type(source_id, JobType.MEDIA)
    session.commit()
    return {"cancelled": cancelled}


@router.post("/sources/{source_id}/media/retry-failed", status_code=202)
def retry_failed_media(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue all FAILED media jobs for the source."""
    job_repo = container.job_repository(session)
    failed_jobs = job_repo.delete_failed_by_source_and_type(source_id, JobType.MEDIA)
    if not failed_jobs:
        logger.info(
            "media.retry_failed: no failed candidates (source_id=%d)", source_id,
        )
        return {"enqueued": 0}

    now = datetime.now(tz=UTC)
    new_jobs = [
        Job(
            id=None,
            job_type=JobType.MEDIA,
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

    logger.info(
        "media.retry_failed: re-enqueued (source_id=%d, count=%d)",
        source_id, len(new_jobs),
    )
    return {"enqueued": len(new_jobs)}
