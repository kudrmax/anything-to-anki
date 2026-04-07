"""ARQ worker module — job functions and WorkerSettings.

Run with: arq backend.infrastructure.workers.WorkerSettings

The worker handles async media extraction and meaning generation jobs
enqueued from the FastAPI app. Each job function wraps the synchronous
use case in a DB session scope and handles permanent vs transient errors:
- PermanentError subclasses → mark_failed, return (no retry)
- Other exceptions → propagate → ARQ retries per max_tries
"""
from __future__ import annotations

import logging
import os
from typing import Any

from arq.connections import RedisSettings

from backend.domain.exceptions import PermanentAIError, PermanentMediaError
from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)


async def extract_media_for_candidate(ctx: dict[str, Any], candidate_id: int) -> None:
    """Single-candidate media extraction job.

    Permanent errors → mark FAILED on candidate_media row and return.
    Transient errors → raise → ARQ retries.
    """
    container: Container = ctx["container"]
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


async def generate_meanings_batch(
    ctx: dict[str, Any], candidate_ids: list[int]
) -> None:
    """Batch meaning generation job (up to 15 candidates).

    Permanent errors → mark batch FAILED.
    Transient errors → raise → ARQ retries.
    """
    container: Container = ctx["container"]
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
    max_tries = 2      # default retries for transient errors
