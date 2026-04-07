from __future__ import annotations

import logging
import time
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
        redis = await container.get_redis_pool()
        for i, batch in enumerate(batches):
            job_id = f"meaning_{source_id}_{i}"
            await redis.enqueue_job(
                "generate_meanings_batch", batch, _job_id=job_id
            )

    total = sum(len(b) for b in batches)
    return {"enqueued": total, "batches": len(batches)}


@router.post("/sources/{source_id}/meanings/cancel")
async def cancel_meaning_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Soft cancel queued meaning generation jobs."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    meaning_repo = container.candidate_meaning_repository(session)
    queued_ids = meaning_repo.get_candidate_ids_by_status(
        source_id, EnrichmentStatus.QUEUED
    )
    if not queued_ids:
        return {"cancelled": 0}

    # Meaning jobs are batched — we abort by batch job_id pattern
    redis = await container.get_redis_pool()
    # Best-effort: try aborting all possible batch job_ids for this source
    # Since we don't track exact batch count, iterate over a reasonable range
    cancelled_batches = 0
    for i in range(100):  # upper bound for batches
        try:
            result = await redis.abort_job(f"meaning_{source_id}_{i}")
            if result:
                cancelled_batches += 1
            else:
                # No more batches found
                if i > 10 and cancelled_batches == 0:
                    break
        except Exception:  # noqa: BLE001
            pass

    # Mark cancelled candidates FAILED so retry-failed can resurrect them.
    meaning_repo.mark_batch_failed(queued_ids, "cancelled by user")
    session.commit()

    return {"cancelled": len(queued_ids)}


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
        return {"enqueued": 0, "batches": 0}

    meaning_repo.mark_queued_bulk(failed_ids)
    session.commit()

    redis = await container.get_redis_pool()
    batch_size = 15
    batches = [failed_ids[i:i + batch_size] for i in range(0, len(failed_ids), batch_size)]
    for i, batch in enumerate(batches):
        # Use retry_N suffix to avoid clashing with previous job_ids
        job_id = f"meaning_{source_id}_retry_{int(time.time())}_{i}"
        await redis.enqueue_job(
            "generate_meanings_batch", batch, _job_id=job_id
        )
    return {"enqueued": len(failed_ids), "batches": len(batches)}
