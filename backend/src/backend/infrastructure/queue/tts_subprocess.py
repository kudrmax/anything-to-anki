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
from backend.infrastructure.queue.claimed_run import ClaimedRun

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container
    from backend.infrastructure.persistence.sqla_job_queue import SqlaJobQueue

logger = logging.getLogger(__name__)

TTS_ONLY: frozenset[JobType] = frozenset({JobType.TTS})


def _claim_next_tts(queue: SqlaJobQueue) -> Job | None:
    run = queue.claim_next_run({}, accepted_types=TTS_ONLY)
    return run[0] if run else None


def _process(container: Container, queue: SqlaJobQueue, job: Job) -> None:
    logger.info("TTS job %d: phrase %s", job.id, job.phrase_id)
    run = ClaimedRun(queue, [job])
    error: str | None = None
    try:
        with run.use_case(container.generate_tts_use_case) as tts:
            for phrase in run.phrases:
                tts.execute_one(phrase)
    except CancelledByUserError as cancelled:
        logger.info("TTS job %d cancelled: %s", job.id, cancelled)
        return
    except Exception as exc:
        logger.exception("TTS job %d failed", job.id)
        error = f"{type(exc).__name__}: {exc}"
    if error is None:
        queue.complete([job])
    else:
        assert job.id is not None
        queue.fail([job.id], error)


def process_tts_run(
    container: Container,
    first_job_id: int,
    worker_alive: Callable[[], bool] = lambda: True,
) -> int:
    """Process the given claimed job, then TTS jobs while they head the queue.
    Stops early once the worker that spawned it is gone: the next worker owns
    the queue then. Returns how many jobs were processed."""
    queue = container.job_queue()
    job = queue.get(first_job_id)
    if job is not None and job.status is not JobStatus.RUNNING:
        job = None  # cancelled before the subprocess started
    processed = 0
    while job is not None:
        _process(container, queue, job)
        processed += 1
        if not worker_alive():
            logger.warning("Worker is gone, TTS subprocess stops")
            break
        job = _claim_next_tts(queue)
    return processed


def main() -> None:
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging
    from backend.infrastructure.persistence.write_gate import WaitOutLongOperation

    configure_logging("tts-worker")
    container = Container(write_gate=WaitOutLongOperation())
    logger.info("TTS subprocess started")
    worker_pid = os.getppid()
    processed = process_tts_run(
        container, int(sys.argv[1]), worker_alive=lambda: os.getppid() == worker_pid,
    )
    logger.info("TTS run finished, exiting (processed %d jobs)", processed)
    container.tts_generator.unload()


if __name__ == "__main__":
    main()
