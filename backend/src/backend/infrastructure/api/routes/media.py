from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

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
        await container.lazy_media_reconciler().schedule(source_id)
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)


@router.post("/sources/{source_id}/media-extraction", status_code=202)
async def start_media_extraction(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.start_media_extraction_use_case(session)
    job = use_case.execute(source_id=source_id)
    session.commit()
    assert job.id is not None
    asyncio.create_task(_run_media_job_background(job.id, container, session_factory))
    return {"job_id": job.id, "status": job.status.value}


@router.get("/sources/{source_id}/media-extraction/{job_id}")
def get_media_extraction_status(
    source_id: int,
    job_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.get_media_extraction_status_use_case(session)
    job = use_case.execute(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status.value,
        "total": job.total_candidates,
        "processed": job.processed_candidates,
        "failed": job.failed_candidates,
        "skipped": job.skipped_candidates,
    }


async def _run_media_job_background(
    job_id: int,
    container: Container,
    session_factory: object,
) -> None:
    # Deprecated: old job-loop flow. Removed in Phase 2 C7.
    raise NotImplementedError("Deprecated, removed in Phase 2 C7")


@router.post("/sources/{source_id}/media/generate", status_code=202)
async def enqueue_media_generation(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue ARQ jobs for all eligible candidates (those with timecodes but no screenshot)."""
    use_case = container.enqueue_media_generation_use_case(session)
    eligible_ids = use_case.execute(source_id)
    session.commit()

    if eligible_ids:
        redis = await container.get_redis_pool()
        for cid in eligible_ids:
            await redis.enqueue_job(
                "extract_media_for_candidate", cid, _job_id=f"media_{cid}"
            )

    return {"enqueued": len(eligible_ids)}


@router.post("/sources/{source_id}/media/cancel")
async def cancel_media_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Soft cancel: abort QUEUED jobs from ARQ. In-flight jobs are not interrupted."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    media_repo = container.candidate_media_repository(session)
    queued_ids = media_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.QUEUED
    )
    if not queued_ids:
        return {"cancelled": 0}

    redis = await container.get_redis_pool()
    cancelled = 0
    for cid in queued_ids:
        try:
            result = await redis.abort_job(f"media_{cid}")
            if result:
                cancelled += 1
        except Exception:  # noqa: BLE001
            pass
    return {"cancelled": cancelled}


@router.post("/sources/{source_id}/media/retry-failed", status_code=202)
async def retry_failed_media(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue all FAILED media jobs for the source."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    media_repo = container.candidate_media_repository(session)
    failed_ids = media_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.FAILED
    )
    if not failed_ids:
        return {"enqueued": 0}

    media_repo.mark_queued_bulk(failed_ids)
    session.commit()

    redis = await container.get_redis_pool()
    for cid in failed_ids:
        await redis.enqueue_job(
            "extract_media_for_candidate", cid, _job_id=f"media_{cid}"
        )
    return {"enqueued": len(failed_ids)}
