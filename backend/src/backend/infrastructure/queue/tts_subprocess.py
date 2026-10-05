"""Standalone TTS worker subprocess.

Spawned by JobWorker with the id of a TTS job it has already claimed.
Loads PyTorch/kokoro once, processes that job and then every TTS job that
reaches the head of the queue, and exits as soon as the head is anything
else. Exiting reclaims all TTS memory and hands the queue back to JobWorker,
so TTS never overtakes older jobs of other types.

Run with: python -m backend.infrastructure.queue.tts_subprocess <job_id>
"""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.queue.claimed_run import ClaimedRun

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

TTS_ONLY: frozenset[JobType] = frozenset({JobType.TTS})


def _claim_next_tts(container: Container) -> Job | None:
    with container.session_scope() as session:
        run = SqlaJobRepository(session).claim_next_run({}, accepted_types=TTS_ONLY)
    return run[0] if run else None


def _process(container: Container, job: Job) -> None:
    assert job.candidate_id is not None
    logger.info("TTS job %d: candidate %d", job.id, job.candidate_id)
    run = ClaimedRun(container, [job])
    error: str | None = None
    try:
        with run.session() as session:
            container.generate_tts_use_case(session).execute_one(job.candidate_id)
    except CancelledByUserError:
        logger.info("TTS job %d cancelled, result dropped", job.id)
        return
    except Exception as exc:
        logger.exception("TTS job %d failed", job.id)
        error = f"{type(exc).__name__}: {exc}"
    with container.session_scope() as session:
        repo = SqlaJobRepository(session)
        if error is None:
            repo.complete([job])
        else:
            assert job.id is not None
            repo.fail([job.id], error)


def process_tts_run(
    container: Container,
    first_job_id: int,
    worker_alive: Callable[[], bool] = lambda: True,
) -> int:
    """Process the given claimed job, then TTS jobs while they head the queue.
    Stops early once the worker that spawned it is gone: the next worker owns
    the queue then. Returns how many jobs were processed."""
    with container.session_scope() as session:
        job = SqlaJobRepository(session).get(first_job_id)
    if job is not None and job.status is not JobStatus.RUNNING:
        job = None  # cancelled before the subprocess started
    processed = 0
    while job is not None:
        _process(container, job)
        processed += 1
        if not worker_alive():
            logger.warning("Worker is gone, TTS subprocess stops")
            break
        job = _claim_next_tts(container)
    return processed


def main() -> None:
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging

    configure_logging("tts-worker")
    container = Container()
    logger.info("TTS subprocess started")
    worker_pid = os.getppid()
    processed = process_tts_run(
        container, int(sys.argv[1]), worker_alive=lambda: os.getppid() == worker_pid,
    )
    logger.info("TTS run finished, exiting (processed %d jobs)", processed)
    container.tts_generator.unload()


if __name__ == "__main__":
    main()
