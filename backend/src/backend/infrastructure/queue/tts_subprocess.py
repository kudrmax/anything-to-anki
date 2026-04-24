"""Standalone TTS worker subprocess.

Spawned by JobWorker when TTS jobs appear in the queue.
Loads PyTorch/kokoro, processes all TTS jobs, exits when done.
This way TTS memory is fully reclaimed after the subprocess exits.

Run with: python -m backend.infrastructure.queue.tts_subprocess
"""
from __future__ import annotations

import asyncio
import logging
import sys

from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

logger = logging.getLogger(__name__)

POLL_DELAY: float = 0.5


async def run() -> None:
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging

    configure_logging("tts-worker")
    container = Container()

    logger.info("TTS subprocess started")
    processed = 0

    while True:
        with container.session_scope() as session:
            job_repo = SqlaJobRepository(session)
            job = job_repo.dequeue_next_by_type(JobType.TTS)

        if job is None:
            if processed > 0:
                logger.info("TTS queue empty, exiting (processed %d jobs)", processed)
                break
            # First poll found nothing — maybe jobs aren't queued yet, wait once
            await asyncio.sleep(POLL_DELAY)
            with container.session_scope() as session:
                job_repo = SqlaJobRepository(session)
                job = job_repo.dequeue_next_by_type(JobType.TTS)
            if job is None:
                logger.info("TTS queue empty, exiting")
                break

        assert job.candidate_id is not None
        assert job.id is not None
        logger.info("TTS job %d: candidate %d", job.id, job.candidate_id)

        try:
            with container.session_scope() as session:
                use_case = container.generate_tts_use_case(session)
                use_case.execute_one(job.candidate_id)
        except Exception as exc:
            logger.exception("TTS job %d failed", job.id)
            with container.session_scope() as session:
                SqlaJobRepository(session).mark_failed_bulk(
                    [job.id], f"{type(exc).__name__}: {exc}",
                )
        else:
            with container.session_scope() as session:
                SqlaJobRepository(session).delete_bulk([job.id])
            processed += 1

    container.tts_generator.unload()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main() or 0)
