"""ARQ worker module — job functions and WorkerSettings.

Run with: arq backend.infrastructure.workers.WorkerSettings

The worker handles async media extraction and meaning generation jobs
enqueued from the FastAPI app. Each job function:
1. Marks candidates as RUNNING in a SEPARATE committed session — so even
   if the use case rolls back on failure, the user still sees that we tried.
2. Runs the use case in its own session.
3. On ANY exception → mark FAILED with the error text and return normally.

We do NOT rely on ARQ automatic retries: ARQ 0.27 only retries on
``arq.Retry`` / ``asyncio.CancelledError`` / ``arq.worker.RetryJob``; a plain
``Exception`` bubbles out as a hard failure and the job is dropped from Redis.
If we let it bubble out, the RUNNING row would never transition to FAILED.
So the worker always catches and marks the row itself. User-initiated retries
go through the UI (re-enqueue of FAILED rows).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from arq.connections import RedisSettings

from backend.domain.exceptions import PermanentAIError, PermanentMediaError
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.container import Container
from backend.infrastructure.logging_setup import configure_logging

configure_logging("worker")
logger = logging.getLogger(__name__)


async def extract_media_for_candidate(ctx: dict[str, Any], candidate_id: int) -> None:
    """Single-candidate media extraction job."""
    container: Container = ctx["container"]

    # Step 1: mark RUNNING in its own committed session
    with container.session_scope() as session:
        container.candidate_media_repository(session).mark_running(candidate_id)

    # Step 1b: verify mark_running took effect (may have been cancelled)
    with container.session_scope() as session:
        media = container.candidate_media_repository(session).get_by_candidate_id(candidate_id)
        if media is None or media.status != EnrichmentStatus.RUNNING:
            logger.info(
                "extract_media_for_candidate: skipped %d (cancelled before start)",
                candidate_id,
            )
            return

    # Step 2: run extraction
    try:
        with container.session_scope() as session:
            use_case = container.media_extraction_use_case(session)
            use_case.execute_one(candidate_id)

        # Check if all media done → clean up YouTube video
        with container.session_scope() as session:
            from backend.infrastructure.persistence.sqla_candidate_repository import (
                SqlaCandidateRepository,
            )
            cand = SqlaCandidateRepository(session).get_by_id(candidate_id)
            if cand is not None:
                cleanup = container.cleanup_youtube_video_use_case(session)
                cleanup.execute(cand.source_id)
    except PermanentMediaError as exc:
        logger.warning(
            "extract_media_for_candidate: permanent error for candidate %d: %s",
            candidate_id, exc,
        )
        with container.session_scope() as session:
            container.candidate_media_repository(session).mark_failed(
                candidate_id, str(exc)
            )
    except Exception as exc:
        logger.exception(
            "extract_media_for_candidate: error for candidate %d", candidate_id,
        )
        with container.session_scope() as session:
            container.candidate_media_repository(session).mark_failed(
                candidate_id, f"{type(exc).__name__}: {exc}"
            )


async def generate_meanings_batch(
    ctx: dict[str, Any], candidate_ids: list[int]
) -> None:
    """Batch meaning generation job (up to 15 candidates)."""
    container: Container = ctx["container"]

    # Step 1: mark all RUNNING in own committed session
    with container.session_scope() as session:
        meaning_repo = container.candidate_meaning_repository(session)
        for cid in candidate_ids:
            meaning_repo.mark_running(cid)

    # Step 1b: verify at least one is still RUNNING (may have been cancelled)
    with container.session_scope() as session:
        meaning_repo = container.candidate_meaning_repository(session)
        still_running = [
            cid for cid in candidate_ids
            if (m := meaning_repo.get_by_candidate_id(cid)) is not None
            and m.status == EnrichmentStatus.RUNNING
        ]
        if not still_running:
            logger.info(
                "generate_meanings_batch: all %d candidates cancelled before start",
                len(candidate_ids),
            )
            return

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
    except Exception as exc:
        logger.exception(
            "generate_meanings_batch: error for batch of %d", len(candidate_ids),
        )
        with container.session_scope() as session:
            container.candidate_meaning_repository(session).mark_batch_failed(
                candidate_ids, f"{type(exc).__name__}: {exc}"
            )


async def download_youtube_video(ctx: dict[str, Any], source_id: int) -> None:
    """Download YouTube video for later media extraction."""
    container: Container = ctx["container"]

    try:
        with container.session_scope() as session:
            use_case = container.download_video_use_case(session)
            use_case.execute(source_id)
    except Exception as exc:
        logger.exception(
            "download_youtube_video: error for source %d", source_id,
        )
        with container.session_scope() as session:
            from backend.infrastructure.persistence.sqla_source_repository import (
                SqlaSourceRepository,
            )
            repo = SqlaSourceRepository(session)
            repo.update_status(
                source_id,
                SourceStatus.ERROR,
                error_message=f"Video download failed: {exc}",
            )


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker starting up")
    ctx["container"] = Container()


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    functions = [extract_media_for_candidate, generate_meanings_batch, download_youtube_video]
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1       # strict sequential processing per user request
    job_timeout = 600  # 10 minutes per job
    max_tries = 1      # no ARQ-level retries; worker handles errors and marks FAILED
