"""SQLite-backed async job worker.

Polls the jobs table, claims the head of the queue and owns the whole job
lifecycle: success → complete, error or timeout → fail, cancel → drop result.

Run with: python -m backend.infrastructure.queue
"""
from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import signal
import sys
from typing import IO, TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError, PermanentError
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.queue.claimed_run import ClaimedRun

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

POLL_DELAY: float = 0.1  # seconds between polls when queue is empty
CARD_STATE_TICK_INTERVAL: float = 60.0  # seconds between time ticks of the card state
# Failed time ticks in a row from which each one is logged as an error: one failure is a
# busy database, several mean the card state is falling behind time.
TICK_FAILURES_TO_ERROR = 3
JOB_TIMEOUT: int = 600  # seconds per run (10 minutes)
AI_BATCH_SIZE: int = 15
RUN_LIMITS: Mapping[JobType, int] = {
    JobType.MEANING: AI_BATCH_SIZE,
    JobType.POLISH: AI_BATCH_SIZE,
}
# A set of sources queues its cards interleaved; an AI batch takes phrases of any source.
MIXED_SOURCE_TYPES: frozenset[JobType] = frozenset({JobType.MEANING, JobType.POLISH})
TIMEOUT_ERROR = "timeout"
NO_AI_RESULT_ERROR = "AI returned no result for this card"
TTS_CRASH_ERROR = "TTS worker exited with code {code}"
LOCK_FILE_NAME = "worker.lock"


class JobWorker:
    """Async polling worker that processes jobs from the SQLite queue."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._queue = container.job_queue()
        self._work = container.session_work()
        self._shutdown = False
        self._tts_process: asyncio.subprocess.Process | None = None

    async def run(self) -> None:
        """Main loop: reconcile on startup, then poll and process jobs."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._request_shutdown)

        self._reconcile_on_startup()
        logger.info("JobWorker started, polling for jobs")

        ticking = asyncio.create_task(self._tick_card_states())
        try:
            while not self._shutdown:
                processed = await self._process_one_job()
                if not processed:
                    await asyncio.sleep(POLL_DELAY)
        finally:
            ticking.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticking

        logger.info("JobWorker shutting down")

    async def _tick_card_states(self) -> None:
        """Writes what time changed in the card state, every `CARD_STATE_TICK_INTERVAL`, on
        its own: the job loop can run one job for minutes. A failed tick is logged and the
        next one tries again; from `TICK_FAILURES_TO_ERROR` failures in a row each is an
        error with the count."""
        failures = 0
        while not self._shutdown:
            try:
                await asyncio.to_thread(self._container.tick_card_states)
            except Exception:
                failures += 1
                level = logging.ERROR if failures >= TICK_FAILURES_TO_ERROR else logging.WARNING
                logger.log(
                    level, "Card state time tick failed (%d in a row)", failures, exc_info=True,
                )
            else:
                failures = 0
            await asyncio.sleep(CARD_STATE_TICK_INTERVAL)

    def _request_shutdown(self) -> None:
        logger.info("Shutdown signal received")
        self._shutdown = True
        if self._tts_process is not None and self._tts_process.returncode is None:
            self._tts_process.terminate()

    def _reconcile_on_startup(self) -> None:
        """Put RUNNING jobs back in line: the worker that ran them is gone.
        Every handler is idempotent, so the work is simply redone."""
        count = self._queue.requeue_running()
        if count:
            logger.warning("Startup reconciliation: requeued %d interrupted jobs", count)

    async def _process_one_job(self) -> bool:
        """Claim and process the head of the queue. Returns True if a run was processed."""
        jobs = self._queue.claim_next_run(RUN_LIMITS, mixed_source_types=MIXED_SOURCE_TYPES)
        if not jobs:
            return False

        run = ClaimedRun(self._queue, jobs)
        head = run.head
        logger.info(
            "Processing %d job(s) from %d: type=%s candidate=%s phrase=%s source=%d",
            len(jobs), head.id, head.job_type.value, head.candidate_id, head.phrase_id,
            head.source_id,
        )
        if head.job_type is JobType.TTS:
            await self._run_tts_subprocess(head)
            return True

        try:
            unanswered = await asyncio.wait_for(
                asyncio.to_thread(self._execute, run), timeout=JOB_TIMEOUT,
            )
        except CancelledByUserError as cancelled:
            logger.info("Run from job %d cancelled: %s", head.id, cancelled)
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
            failed = [j for j in jobs if j.phrase_id in unanswered]
            self._fail(failed, NO_AI_RESULT_ERROR)
            self._complete([j for j in jobs if j not in failed])
        return True

    # ------------------------------------------------------------------
    # Work — runs in a thread
    # ------------------------------------------------------------------

    def _execute(self, run: ClaimedRun) -> set[int]:
        """Do the run's work. Returns the phrases left without a result."""
        head = run.head
        c = self._container
        match head.job_type:
            case JobType.MEANING:
                with run.use_case(c.meaning_generation_use_case) as meaning:
                    return set(meaning.execute_batch(run.phrases, run.still_wanted))
            case JobType.POLISH:
                with run.use_case(c.phrase_polish_use_case) as polish:
                    return set(polish.execute_batch(run.phrases, run.still_wanted))
            case JobType.MEDIA:
                with run.use_case(c.media_extraction_use_case) as media:
                    for phrase in run.phrases:
                        media.execute_one(phrase)
                with self._work.open(c.cleanup_youtube_video_use_case) as cleanup:
                    cleanup.execute(head.source_id)
            case JobType.PRONUNCIATION:
                assert head.candidate_id is not None
                with run.use_case(c.download_pronunciation_use_case) as pronunciation:
                    pronunciation.execute_one(head.candidate_id)
            case JobType.VIDEO_DOWNLOAD:
                with run.use_case(c.download_video_use_case) as video:
                    video.execute(head.source_id)
            case JobType.TOPIC_TARGETS:
                with run.use_case(c.generate_topic_targets_use_case) as topic:
                    topic.execute(head.source_id)
            case JobType.TTS:
                raise AssertionError("TTS runs in its own subprocess")
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
        self._queue.fail_running(JobType.TTS, TTS_CRASH_ERROR.format(code=returncode))

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def _fail(self, jobs: list[Job], error: str) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if not job_ids:
            return
        self._queue.fail(job_ids, error)

    def _complete(self, jobs: list[Job]) -> None:
        if not jobs:
            return
        self._queue.complete(jobs)


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
    from backend.infrastructure.startup_heap import freeze_startup_heap

    configure_logging("worker")
    lock = _acquire_single_worker_lock()
    try:
        worker = JobWorker(Container())
        freeze_startup_heap()
        await worker.run()
    finally:
        lock.close()


if __name__ == "__main__":
    asyncio.run(main())
