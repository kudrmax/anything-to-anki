from __future__ import annotations

import os
from datetime import UTC
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
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

    media_repo.mark_batch_failed(affected_ids, "cancelled by user")
    session.commit()

    # Best-effort: abort per-candidate jobs that haven't started yet
    redis = await container.get_redis_pool()
    aborted = 0
    for cid in affected_ids:
        try:
            result = await redis.abort_job(f"media_{cid}")
            if result:
                aborted += 1
        except Exception:  # noqa: BLE001
            pass
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
    return {"enqueued": len(failed_ids)}
