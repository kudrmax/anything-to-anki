from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

from backend.application.dto.generation_dtos import (  # noqa: TC001
    GenerationQueueDTO,
    StartGenerationRequest,
)
from backend.domain.exceptions import GenerationAlreadyRunningError, NoActiveCandidatesError
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/start", status_code=202)
async def start_generation(
    request: StartGenerationRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> GenerationQueueDTO:
    try:
        use_case = container.start_generation_use_case(session)
        queue_dto = use_case.execute(request.source_id)
        session.commit()
    except GenerationAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except NoActiveCandidatesError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Launch first job if exists
    if queue_dto.pending_jobs:
        first_job_id = queue_dto.pending_jobs[0].id
        asyncio.create_task(
            _run_generation_background(
                first_job_id, request.source_id, container, session_factory
            )
        )

    return queue_dto


@router.post("/{job_id}/stop")
def stop_generation(
    job_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    use_case = container.stop_generation_use_case(session)
    use_case.execute(job_id)
    session.commit()
    return {"status": "pausing"}


@router.get("/status")
def get_generation_status(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> Response:
    use_case = container.get_generation_status_use_case(session)
    result = use_case.execute()
    if result is None:
        return Response(status_code=204)
    return JSONResponse(content=result.model_dump(mode="json", by_alias=True))


async def _run_generation_background(
    job_id: int,
    source_id: int | None,
    container: Container,
    session_factory: object,
) -> None:
    # Deprecated: old job-loop flow. Removed in Phase 2 C7.
    raise NotImplementedError("Deprecated, removed in Phase 2 C7")


@router.post("/sources/{source_id}/meanings/generate", status_code=202)
async def enqueue_meaning_generation(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue ARQ jobs for meaning generation, batched by 15."""
    use_case = container.enqueue_meaning_generation_use_case(session)
    batches = use_case.execute(source_id)
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
    import time

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
