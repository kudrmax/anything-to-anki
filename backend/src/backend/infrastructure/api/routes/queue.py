from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from backend.application.dto.queue_dtos import (  # noqa: TC001
    CancelRequestDTO,
    QueueFailedDTO,
    QueueGlobalSummaryDTO,
    QueueOrderDTO,
    RetryRequestDTO,
)
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.infrastructure.api.dependencies import get_container, get_db_session
from backend.infrastructure.api.routes.media import _flush_and_abort_jobs, _register_job_ids

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])

_MEANING_BATCH_SIZE = 15

# (container repo method, redis job_type key, arq function, batched?)
_JOB_TYPE_CONFIG: dict[str, tuple[str, str, str, bool]] = {
    "meanings": ("candidate_meaning_repository", "meaning", "generate_meanings_batch", True),
    "media": ("candidate_media_repository", "media", "extract_media_for_candidate", False),
    "pronunciation": (
        "candidate_pronunciation_repository", "pronunciation",
        "download_pronunciation_for_candidate", False,
    ),
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


# ── ACTION endpoints ────────────────────────────────────────────────
#
# Cancel and retry reuse the SAME logic as per-source endpoints in
# generation.py / media.py / pronunciation.py:
#   cancel = mark_batch_cancelled in DB + _flush_and_abort_jobs in Redis
#   retry  = mark_queued_bulk in DB + enqueue_job in Redis


@router.post("/cancel")
async def cancel_queued(
    body: CancelRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued+running jobs. Same logic as per-source cancel endpoints."""
    config = _JOB_TYPE_CONFIG.get(body.job_type)
    if config is None:
        return {"cancelled": 0}

    repo_method, redis_key, _, _ = config
    repo: Any = getattr(container, repo_method)(session)
    redis: Any = await container.get_redis_pool()

    source_ids = _resolve_source_ids(
        repo, body.source_id, [EnrichmentStatus.QUEUED, EnrichmentStatus.RUNNING],
    )

    total = 0
    for sid in source_ids:
        queued = repo.get_candidate_ids_by_status(sid, EnrichmentStatus.QUEUED)
        running = repo.get_candidate_ids_by_status(sid, EnrichmentStatus.RUNNING)
        affected = queued + running
        if not affected:
            continue
        repo.mark_batch_cancelled(affected)
        await _flush_and_abort_jobs(redis, sid, redis_key)
        total += len(affected)

    if total:
        session.commit()
    return {"cancelled": total}


@router.post("/retry", status_code=202)
async def retry_failed(
    body: RetryRequestDTO,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue failed jobs. Same logic as per-source retry endpoints."""
    config = _JOB_TYPE_CONFIG.get(body.job_type)
    if config is None:
        return {"retried": 0}

    repo_method, redis_key, arq_function, batched = config
    repo: Any = getattr(container, repo_method)(session)
    redis: Any = await container.get_redis_pool()

    # Collect per-source failed IDs
    per_source: dict[int, list[int]] = {}

    if body.error_text is not None:
        # Retry by error text — get_candidate_ids_by_error returns flat list
        # Need to group by source. Use source_ids from failed groups.
        failed_ids = repo.get_candidate_ids_by_error(
            body.error_text, source_id=body.source_id,
        )
        if body.source_id is not None:
            per_source[body.source_id] = failed_ids
        else:
            # Group by discovering sources from error groups
            source_ids = _resolve_source_ids(repo, None, [EnrichmentStatus.FAILED])
            for sid in source_ids:
                sid_ids = [
                    cid for cid in repo.get_candidate_ids_by_error(
                        body.error_text, source_id=sid,
                    )
                ]
                if sid_ids:
                    per_source[sid] = sid_ids
    else:
        source_ids = _resolve_source_ids(repo, body.source_id, [EnrichmentStatus.FAILED])
        for sid in source_ids:
            ids = repo.get_candidate_ids_by_status(sid, EnrichmentStatus.FAILED)
            if ids:
                per_source[sid] = ids

    all_ids = [cid for ids in per_source.values() for cid in ids]
    if not all_ids:
        return {"retried": 0}

    # Mark queued in DB + commit
    repo.mark_queued_bulk(all_ids)
    session.commit()

    # Enqueue in Redis per source
    ts_ms = int(time.time() * 1000)
    base = datetime.now(tz=UTC)
    for sid, cids in per_source.items():
        await _enqueue_for_source(
            redis, sid, cids, redis_key, arq_function, batched, ts_ms, base,
        )

    return {"retried": len(all_ids)}


# ── Helpers ─────────────────────────────────────────────────────────


async def _enqueue_for_source(
    redis: Any,  # noqa: ANN401
    source_id: int,
    candidate_ids: list[int],
    redis_key: str,
    arq_function: str,
    batched: bool,
    ts_ms: int,
    base: datetime,
) -> None:
    """Enqueue jobs in Redis for one source. Mirrors existing retry endpoints."""
    job_ids: list[str] = []
    if batched:
        batches = [
            candidate_ids[i:i + _MEANING_BATCH_SIZE]
            for i in range(0, len(candidate_ids), _MEANING_BATCH_SIZE)
        ]
        for i, batch in enumerate(batches):
            job_id = f"{redis_key}_{source_id}_retry_{ts_ms}_{i:04d}"
            await redis.enqueue_job(
                arq_function, batch,
                _job_id=job_id, _defer_until=base + timedelta(milliseconds=i),
            )
            job_ids.append(job_id)
    else:
        for i, cid in enumerate(candidate_ids):
            job_id = f"{redis_key}_{source_id}_{cid}_retry_{ts_ms}"
            await redis.enqueue_job(
                arq_function, cid,
                _job_id=job_id, _defer_until=base + timedelta(milliseconds=i),
            )
            job_ids.append(job_id)
    await _register_job_ids(redis, source_id, redis_key, job_ids)


def _resolve_source_ids(
    repo: Any,  # noqa: ANN401
    source_id: int | None,
    statuses: list[EnrichmentStatus],
) -> list[int]:
    """Determine which source IDs to operate on.

    If source_id given, returns [source_id].
    Otherwise discovers sources with activity via repo methods.
    """
    if source_id is not None:
        return [source_id]
    source_ids: set[int] = set()
    for status in statuses:
        sids = repo.get_source_ids_by_enrichment_status(status)
        source_ids.update(sids)
    return list(source_ids)
