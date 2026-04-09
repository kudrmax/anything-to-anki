from __future__ import annotations

import logging
import time
from datetime import UTC
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

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
async def enqueue_meaning_generation(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue ARQ jobs for meaning generation, batched by 15.
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

    if batches:
        from datetime import datetime, timedelta
        redis = await container.get_redis_pool()
        # Unique timestamp prefix avoids ARQ deduplication on re-enqueue.
        # _defer_until with microsecond offset gives each batch a UNIQUE
        # Redis ZSET score so worker pops them in enqueue order (otherwise
        # equal scores fall back to lexicographic, e.g. ..._10 before ..._2).
        ts_ms = int(time.time() * 1000)
        base = datetime.now(tz=UTC)
        for i, batch in enumerate(batches):
            job_id = f"meaning_{source_id}_{ts_ms}_{i:04d}"
            await redis.enqueue_job(
                "generate_meanings_batch",
                batch,
                _job_id=job_id,
                _defer_until=base + timedelta(milliseconds=i),
            )

    total = sum(len(b) for b in batches)
    return {"enqueued": total, "batches": len(batches)}


@router.post("/sources/{source_id}/meanings/cancel")
async def cancel_meaning_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued AND running meaning generation jobs.

    Marks both QUEUED and RUNNING candidates as FAILED with 'cancelled by user'.
    The use case checks the row status before its final upsert, so any in-flight
    worker job will see the cancelled status and skip writing its result.
    """
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    meaning_repo = container.candidate_meaning_repository(session)
    queued_ids = meaning_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.QUEUED
    )
    running_ids = meaning_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.RUNNING
    )
    affected_ids = queued_ids + running_ids
    if not affected_ids:
        return {"cancelled": 0}

    # Mark all FAILED with cancellation marker — worker's pre-upsert guard
    # will see this status and skip writing results for the running batch.
    meaning_repo.mark_batch_failed(affected_ids, "cancelled by user")
    session.commit()

    # Best-effort: also abort batch jobs that haven't started yet
    redis = await container.get_redis_pool()
    cancelled_batches = 0
    for i in range(100):
        try:
            result = await redis.abort_job(f"meaning_{source_id}_{i}")
            if result:
                cancelled_batches += 1
            elif i > 10 and cancelled_batches == 0:
                break
        except Exception:  # noqa: BLE001
            logger.warning(
                "generation.cancel: best-effort batch abort failed "
                "(source_id=%d, batch_index=%d)",
                source_id,
                i,
                exc_info=True,
            )

    return {"cancelled": len(affected_ids)}


@router.post("/sources/{source_id}/meanings/retry-failed", status_code=202)
async def retry_failed_meanings(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue failed meaning generation jobs, batched by 15."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    meaning_repo = container.candidate_meaning_repository(session)
    failed_ids = meaning_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.FAILED
    )
    if not failed_ids:
        logger.info(
            "generation.retry_failed: no failed candidates (source_id=%d)", source_id,
        )
        return {"enqueued": 0, "batches": 0}

    meaning_repo.mark_queued_bulk(failed_ids)
    session.commit()

    from datetime import datetime, timedelta
    redis = await container.get_redis_pool()
    batch_size = 15
    batches = [failed_ids[i:i + batch_size] for i in range(0, len(failed_ids), batch_size)]
    ts_ms = int(time.time() * 1000)
    base = datetime.now(tz=UTC)
    for i, batch in enumerate(batches):
        job_id = f"meaning_{source_id}_retry_{ts_ms}_{i:04d}"
        await redis.enqueue_job(
            "generate_meanings_batch",
            batch,
            _job_id=job_id,
            _defer_until=base + timedelta(milliseconds=i),
        )
    logger.info(
        "generation.retry_failed: re-enqueued "
        "(source_id=%d, total=%d, batches=%d)",
        source_id, len(failed_ids), len(batches),
    )
    return {"enqueued": len(failed_ids), "batches": len(batches)}
