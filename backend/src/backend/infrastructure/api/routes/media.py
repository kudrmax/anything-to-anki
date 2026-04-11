from __future__ import annotations

import logging
import os
from datetime import UTC
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["media"])

DEFAULT_QUEUE_NAME = "arq:queue"


async def _flush_media_jobs(redis: Any, prefixes: set[str]) -> int:  # noqa: ANN401 — arq has no type stubs
    """Remove media jobs whose job_id starts with any of *prefixes* from the arq queue."""
    queued = await redis.queued_jobs()
    removed = 0
    for job in queued:
        if job.job_id and any(job.job_id.startswith(p) for p in prefixes):
            await redis.zrem(DEFAULT_QUEUE_NAME, job.job_id)
            await redis.delete(f"arq:job:{job.job_id}")
            removed += 1
    return removed


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
async def enqueue_media_generation(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue ARQ jobs for all eligible candidates (those with timecodes but no screenshot).
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

    if eligible_ids:
        import time
        from datetime import datetime, timedelta
        redis = await container.get_redis_pool()
        # Unique timestamp prefix avoids ARQ deduplication; _defer_until with
        # microsecond offset gives each job a unique Redis ZSET score so they
        # are popped in enqueue order (otherwise lex order shuffles them).
        ts_ms = int(time.time() * 1000)
        base = datetime.now(tz=UTC)
        for i, cid in enumerate(eligible_ids):
            await redis.enqueue_job(
                "extract_media_for_candidate",
                cid,
                _job_id=f"media_{cid}_{ts_ms}",
                _defer_until=base + timedelta(milliseconds=i),
            )

    return {"enqueued": len(eligible_ids)}


@router.post("/sources/{source_id}/media/cancel")
async def cancel_media_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued AND running media extraction jobs.

    Marks both QUEUED and RUNNING candidates as FAILED with 'cancelled by user'.
    The use case checks the row status before its final upsert, so any in-flight
    worker job will see the cancelled status and skip writing its result.
    """
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    media_repo = container.candidate_media_repository(session)
    queued_ids = media_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.QUEUED
    )
    running_ids = media_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.RUNNING
    )
    affected_ids = queued_ids + running_ids
    if not affected_ids:
        return {"cancelled": 0}

    media_repo.mark_batch_cancelled(affected_ids)
    session.commit()

    # Clean orphaned jobs from Redis queue (stateless transport cleanup)
    redis = await container.get_redis_pool()
    prefixes = {f"media_{cid}_" for cid in affected_ids}
    removed = await _flush_media_jobs(redis, prefixes)
    if removed:
        logger.info(
            "cancel_media_queue: removed %d jobs from Redis (source_id=%d)",
            removed, source_id,
        )

    return {"cancelled": len(affected_ids)}


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
        logger.info(
            "media.retry_failed: no failed candidates (source_id=%d)", source_id,
        )
        return {"enqueued": 0}

    media_repo.mark_queued_bulk(failed_ids)
    session.commit()

    import time
    from datetime import datetime, timedelta
    redis = await container.get_redis_pool()
    ts_ms = int(time.time() * 1000)
    base = datetime.now(tz=UTC)
    for i, cid in enumerate(failed_ids):
        await redis.enqueue_job(
            "extract_media_for_candidate",
            cid,
            _job_id=f"media_{cid}_retry_{ts_ms}",
            _defer_until=base + timedelta(milliseconds=i),
        )
    logger.info(
        "media.retry_failed: re-enqueued (source_id=%d, count=%d)",
        source_id, len(failed_ids),
    )
    return {"enqueued": len(failed_ids)}
