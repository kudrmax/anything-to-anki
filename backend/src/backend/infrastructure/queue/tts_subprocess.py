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
import sys
from typing import TYPE_CHECKING

from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

if TYPE_CHECKING:
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


def run(first_job_id: int) -> None:
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging

    configure_logging("tts-worker")
    container = Container()
    logger.info("TTS subprocess started")

    with container.session_scope() as session:
        job = SqlaJobRepository(session).get(first_job_id)
    processed = 0
    while job is not None:
        _process(container, job)
        processed += 1
        job = _claim_next_tts(container)

    logger.info("TTS run finished, exiting (processed %d jobs)", processed)
    container.tts_generator.unload()


def main() -> None:
    run(int(sys.argv[1]))


if __name__ == "__main__":
    main()
