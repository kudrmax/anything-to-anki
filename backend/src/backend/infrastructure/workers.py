"""ARQ worker module — job functions and WorkerSettings.

Run with: arq backend.infrastructure.workers.WorkerSettings

The worker handles async media extraction and meaning generation jobs
enqueued from the FastAPI app. Each job function:
1. Marks candidates as RUNNING in a SEPARATE committed session — so even
   if the use case rolls back on failure, the user still sees that we tried.
2. Runs the use case in its own session.
3. On PermanentError → mark FAILED and return (no retry).
4. On other exceptions → re-raise so ARQ retries (per max_tries),
   except on the LAST try where we mark FAILED ourselves.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from arq.connections import RedisSettings

from backend.domain.exceptions import PermanentAIError, PermanentMediaError
from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

_MAX_TRIES = 2


async def extract_media_for_candidate(ctx: dict[str, Any], candidate_id: int) -> None:
    """Single-candidate media extraction job."""
    container: Container = ctx["container"]
    job_try = ctx.get("job_try", 1)

    # Step 1: mark RUNNING in its own committed session
    with container.session_scope() as session:
        container.candidate_media_repository(session).mark_running(candidate_id)

    # Step 2: run extraction
    try:
        with container.session_scope() as session:
            use_case = container.media_extraction_use_case(session)
            use_case.execute_one(candidate_id)
    except PermanentMediaError as exc:
        logger.warning(
            "extract_media_for_candidate: permanent error for candidate %d: %s",
            candidate_id, exc,
        )
        with container.session_scope() as session:
            container.candidate_media_repository(session).mark_failed(
                candidate_id, str(exc)
            )
        return
    except Exception as exc:
        if job_try >= _MAX_TRIES:
            logger.warning(
                "extract_media_for_candidate: exhausted retries for candidate %d: %s",
                candidate_id, exc,
            )
            with container.session_scope() as session:
                container.candidate_media_repository(session).mark_failed(
                    candidate_id, f"Failed after {_MAX_TRIES} attempts: {exc}"
                )
            return
        raise  # let ARQ retry


async def generate_meanings_batch(
    ctx: dict[str, Any], candidate_ids: list[int]
) -> None:
    """Batch meaning generation job (up to 15 candidates)."""
    container: Container = ctx["container"]
    job_try = ctx.get("job_try", 1)

    # Step 1: mark all RUNNING in own committed session
    with container.session_scope() as session:
        meaning_repo = container.candidate_meaning_repository(session)
        for cid in candidate_ids:
            meaning_repo.mark_running(cid)

    # Step 2: run generation
    try:
        with container.session_scope() as session:
            use_case = container.meaning_generation_use_case(session)
            use_case.execute_batch(candidate_ids)
    except PermanentAIError as exc:
        logger.warning(
            "generate_meanings_batch: permanent error for batch of %d: %s",
            len(candidate_ids), exc,
        )
        with container.session_scope() as session:
            container.candidate_meaning_repository(session).mark_batch_failed(
                candidate_ids, str(exc)
            )
        return
    except Exception as exc:
        if job_try >= _MAX_TRIES:
            logger.warning(
                "generate_meanings_batch: exhausted retries for batch of %d: %s",
                len(candidate_ids), exc,
            )
            with container.session_scope() as session:
                container.candidate_meaning_repository(session).mark_batch_failed(
                    candidate_ids, f"Failed after {_MAX_TRIES} attempts: {exc}"
                )
            return
        raise  # let ARQ retry


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker starting up")
    ctx["container"] = Container()


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    functions = [extract_media_for_candidate, generate_meanings_batch]
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1       # strict sequential processing per user request
    job_timeout = 600  # 10 minutes per job
    max_tries = _MAX_TRIES
