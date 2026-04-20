from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.infrastructure.api.dependencies import get_container, get_db_session
from backend.infrastructure.api.routes.media import _flush_and_abort_jobs, _register_job_ids

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["pronunciation"])


@router.post("/sources/{source_id}/pronunciation/generate", status_code=202)
async def enqueue_pronunciation_download(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue pronunciation download jobs for all eligible candidates."""
    use_case = container.enqueue_pronunciation_download_use_case(session)
    eligible_ids = use_case.execute(source_id)
    session.commit()

    if eligible_ids:
        redis = await container.get_redis_pool()
        ts_ms = int(time.time() * 1000)
        base = datetime.now(tz=UTC)
        job_ids: list[str] = []
        for i, cid in enumerate(eligible_ids):
            job_id = f"pron_{cid}_{ts_ms}"
            await redis.enqueue_job(
                "download_pronunciation_for_candidate",
                cid,
                _job_id=job_id,
                _defer_until=base + timedelta(milliseconds=i),
            )
            job_ids.append(job_id)
        await _register_job_ids(redis, source_id, "pronunciation", job_ids)

    return {"enqueued": len(eligible_ids)}


@router.post("/sources/{source_id}/pronunciation/cancel")
async def cancel_pronunciation_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued and running pronunciation download jobs."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus

    pron_repo = container.candidate_pronunciation_repository(session)
    queued = pron_repo.get_candidate_ids_by_status(source_id, EnrichmentStatus.QUEUED)
    running = pron_repo.get_candidate_ids_by_status(source_id, EnrichmentStatus.RUNNING)
    affected = queued + running
    if not affected:
        return {"cancelled": 0}

    pron_repo.mark_batch_cancelled(affected)
    session.commit()

    redis = await container.get_redis_pool()
    await _flush_and_abort_jobs(redis, source_id, "pronunciation")

    return {"cancelled": len(affected)}


@router.post("/sources/{source_id}/pronunciation/retry-failed", status_code=202)
async def retry_failed_pronunciation(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue all FAILED pronunciation jobs."""
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus

    pron_repo = container.candidate_pronunciation_repository(session)
    failed_ids = pron_repo.get_candidate_ids_by_status(source_id, EnrichmentStatus.FAILED)
    if not failed_ids:
        return {"enqueued": 0}

    pron_repo.mark_queued_bulk(failed_ids)
    session.commit()

    redis = await container.get_redis_pool()
    ts_ms = int(time.time() * 1000)
    base = datetime.now(tz=UTC)
    job_ids: list[str] = []
    for i, cid in enumerate(failed_ids):
        job_id = f"pron_{cid}_retry_{ts_ms}"
        await redis.enqueue_job(
            "download_pronunciation_for_candidate",
            cid,
            _job_id=job_id,
            _defer_until=base + timedelta(milliseconds=i),
        )
        job_ids.append(job_id)
    await _register_job_ids(redis, source_id, "pronunciation", job_ids)

    return {"enqueued": len(failed_ids)}
