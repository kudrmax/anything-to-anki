"""SQLite-backed async job worker.

Polls the jobs table, claims the head of the queue and owns the whole job
lifecycle: success → complete, error or timeout → fail, cancel → drop result.

Run with: python -m backend.infrastructure.queue
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import sys
from typing import IO, TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError, PermanentError
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.queue.claimed_run import ClaimedRun

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

POLL_DELAY: float = 0.1  # seconds between polls when queue is empty
JOB_TIMEOUT: int = 600  # seconds per run (10 minutes)
AI_BATCH_SIZE: int = 15
RUN_LIMITS: Mapping[JobType, int] = {
    JobType.MEANING: AI_BATCH_SIZE,
    JobType.POLISH: AI_BATCH_SIZE,
}
TIMEOUT_ERROR = "timeout"
NO_AI_RESULT_ERROR = "AI returned no result for this card"
TTS_CRASH_ERROR = "TTS worker exited with code {code}"
LOCK_FILE_NAME = "worker.lock"


class JobWorker:
    """Async polling worker that processes jobs from the SQLite queue."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._shutdown = False
        self._tts_process: asyncio.subprocess.Process | None = None

    async def run(self) -> None:
        """Main loop: reconcile on startup, then poll and process jobs."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._request_shutdown)

        self._reconcile_on_startup()
        logger.info("JobWorker started, polling for jobs")

        while not self._shutdown:
            processed = await self._process_one_job()
            if not processed:
                await asyncio.sleep(POLL_DELAY)

        logger.info("JobWorker shutting down")

    def _request_shutdown(self) -> None:
        logger.info("Shutdown signal received")
        self._shutdown = True
        if self._tts_process is not None and self._tts_process.returncode is None:
            self._tts_process.terminate()

    def _reconcile_on_startup(self) -> None:
        """Put RUNNING jobs back in line: the worker that ran them is gone.
        Every handler is idempotent, so the work is simply redone."""
        with self._container.session_scope() as session:
            count = SqlaJobRepository(session).requeue_running()
        if count:
            logger.warning("Startup reconciliation: requeued %d interrupted jobs", count)

    async def _process_one_job(self) -> bool:
        """Claim and process the head of the queue. Returns True if a run was processed."""
        with self._container.session_scope() as session:
            jobs = SqlaJobRepository(session).claim_next_run(RUN_LIMITS)
        if not jobs:
            return False

        run = ClaimedRun(self._container, jobs)
        head = run.head
        logger.info(
            "Processing %d job(s) from %d: type=%s candidate=%s source=%d",
            len(jobs), head.id, head.job_type.value, head.candidate_id, head.source_id,
        )
        if head.job_type is JobType.TTS:
            await self._run_tts_subprocess(head)
            return True

        try:
            unanswered = await asyncio.wait_for(
                asyncio.to_thread(self._execute, run), timeout=JOB_TIMEOUT,
            )
        except CancelledByUserError:
            logger.info("Run from job %d cancelled, result dropped", head.id)
        except TimeoutError:
            logger.warning("Run from job %d timed out", head.id)
            self._fail(jobs, TIMEOUT_ERROR)
        except PermanentError as exc:
            logger.warning("Run from job %d permanent error: %s", head.id, exc)
            self._fail(jobs, str(exc))
        except Exception as exc:
            logger.exception("Run from job %d unexpected error", head.id)
            self._fail(jobs, f"{type(exc).__name__}: {exc}")
        else:
            failed = [j for j in jobs if j.candidate_id in unanswered]
            self._fail(failed, NO_AI_RESULT_ERROR)
            self._complete([j for j in jobs if j not in failed])
        return True

    # ------------------------------------------------------------------
    # Work — runs in a thread
    # ------------------------------------------------------------------

    def _execute(self, run: ClaimedRun) -> set[int]:
        """Do the run's work. Returns candidates left without a result."""
        head = run.head
        c = self._container
        with run.session() as session:
            match head.job_type:
                case JobType.MEANING:
                    return set(c.meaning_generation_use_case(session).execute_batch(
                        run.candidate_ids, run.still_wanted,
                    ))
                case JobType.POLISH:
                    return set(c.phrase_polish_use_case(session).execute_batch(
                        run.candidate_ids, run.still_wanted,
                    ))
                case JobType.MEDIA:
                    assert head.candidate_id is not None
                    c.media_extraction_use_case(session).execute_one(head.candidate_id)
                case JobType.PRONUNCIATION:
                    assert head.candidate_id is not None
                    c.download_pronunciation_use_case(session).execute_one(head.candidate_id)
                case JobType.VIDEO_DOWNLOAD:
                    c.download_video_use_case(session).execute(head.source_id)
                case JobType.TOPIC_TARGETS:
                    c.generate_topic_targets_use_case(session).execute(head.source_id)
                case JobType.TTS:
                    raise AssertionError("TTS runs in its own subprocess")
        if head.job_type is JobType.MEDIA:
            with c.session_scope() as session:
                c.cleanup_youtube_video_use_case(session).execute(head.source_id)
        return set()

    # ------------------------------------------------------------------
    # TTS subprocess
    # ------------------------------------------------------------------

    async def _run_tts_subprocess(self, job: Job) -> None:
        """Hand the claimed TTS job to a subprocess.

        The subprocess loads PyTorch/kokoro, processes this job and every TTS
        job that reaches the head of the queue after it, then exits — freeing
        all TTS memory. The worker waits, so no other job runs meanwhile.
        """
        assert job.id is not None
        logger.info("Spawning TTS subprocess")
        self._tts_process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "backend.infrastructure.queue.tts_subprocess",
            str(job.id),
        )
        returncode = await self._tts_process.wait()
        self._tts_process = None
        if returncode == 0:
            logger.info("TTS subprocess finished successfully")
            return
        logger.error("TTS subprocess exited with code %d", returncode)
        if self._shutdown:
            return  # interrupted on purpose; the next start requeues its job
        with self._container.session_scope() as session:
            SqlaJobRepository(session).fail_running(
                JobType.TTS, TTS_CRASH_ERROR.format(code=returncode),
            )

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def _fail(self, jobs: list[Job], error: str) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if not job_ids:
            return
        with self._container.session_scope() as session:
            SqlaJobRepository(session).fail(job_ids, error)

    def _complete(self, jobs: list[Job]) -> None:
        if not jobs:
            return
        with self._container.session_scope() as session:
            SqlaJobRepository(session).complete(jobs)


def _acquire_single_worker_lock() -> IO[str]:
    """Hold an exclusive lock for the process lifetime: one worker per data dir.

    Two workers would requeue each other's running jobs and claim the queue
    concurrently. The OS drops the lock when the process dies, however it dies.
    """
    data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
    os.makedirs(data_dir, exist_ok=True)
    # Not a `with` block: closing the file releases the lock, so it stays open.
    lock_file = open(os.path.join(data_dir, LOCK_FILE_NAME), "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("Another worker is already running for %s, exiting", data_dir)
        sys.exit(1)
    return lock_file


async def main() -> None:
    """Entry point for ``python -m backend.infrastructure.queue``."""
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging

    configure_logging("worker")
    lock = _acquire_single_worker_lock()
    try:
        worker = JobWorker(Container())
        await worker.run()
    finally:
        lock.close()


if __name__ == "__main__":
    asyncio.run(main())
