"""SQLite-backed async job worker.

Replaces arq+Redis. Polls the jobs table for QUEUED work,
dispatches to handlers, manages lifecycle (done→delete, fail→mark).

Run with: python -m backend.infrastructure.queue.job_worker
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError, PermanentAIError, PermanentMediaError
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

POLL_DELAY: float = 0.1  # seconds between polls when queue is empty
JOB_TIMEOUT: int = 600  # seconds per job (10 minutes)
AI_BATCH_SIZE: int = 15
RUN_LIMITS: Mapping[JobType, int] = {
    JobType.MEANING: AI_BATCH_SIZE,
    JobType.POLISH: AI_BATCH_SIZE,
}


class JobWorker:
    """Async polling worker that processes jobs from the SQLite queue."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._shutdown = False

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

    def _reconcile_on_startup(self) -> None:
        """Mark all RUNNING jobs as FAILED — they were interrupted by restart."""
        with self._container.session_scope() as session:
            job_repo = SqlaJobRepository(session)
            count = job_repo.fail_all_running("interrupted by worker restart")
        if count:
            logger.warning(
                "Startup reconciliation: reset %d RUNNING jobs to FAILED", count,
            )

    async def _process_one_job(self) -> bool:
        """Dequeue and process one job. Returns True if a job was processed."""
        with self._container.session_scope() as session:
            job_repo = SqlaJobRepository(session)
            run = job_repo.claim_next_run(RUN_LIMITS)

        if not run:
            return False
        job = run[0]

        logger.info(
            "Processing job %d: type=%s candidate=%s source=%d",
            job.id, job.job_type.value, job.candidate_id, job.source_id,
        )

        try:
            match job.job_type:
                case JobType.MEANING:
                    # Meaning handler manages its own batch success/failure
                    await self._handle_ai_batch(run, self._run_meaning_batch)
                    return True
                case JobType.MEDIA:
                    await self._handle_media(job)
                case JobType.PRONUNCIATION:
                    await self._handle_pronunciation(job)
                case JobType.VIDEO_DOWNLOAD:
                    await self._handle_video_download(job)
                case JobType.POLISH:
                    # Polish handler manages its own batch success/failure
                    await self._handle_ai_batch(run, self._run_polish_batch)
                    return True
                case JobType.TOPIC_TARGETS:
                    await self._handle_topic_targets(job)
                case JobType.TTS:
                    # TTS handler manages its own lifecycle via subprocess
                    await self._handle_tts(job)
                    return True
        except CancelledByUserError:
            logger.info("Job %d cancelled by user", job.id)
        except (PermanentAIError, PermanentMediaError) as exc:
            logger.warning("Job %d permanent error: %s", job.id, exc)
            self._mark_jobs_failed([job], str(exc))
        except Exception as exc:
            logger.exception("Job %d unexpected error", job.id)
            self._mark_jobs_failed([job], f"{type(exc).__name__}: {exc}")
        else:
            self._delete_jobs([job])

        return True

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_ai_batch(
        self, all_jobs: list[Job], run: Callable[[list[int], Job], None],
    ) -> None:
        """One AI call for a claimed run of same-type, same-source jobs.

        Manages its own success/failure because the outer handler only knows
        about the primary job.
        """
        job = all_jobs[0]
        kind = job.job_type.value
        candidate_ids = [j.candidate_id for j in all_jobs if j.candidate_id is not None]

        if not candidate_ids:
            self._delete_jobs(all_jobs)
            return

        try:
            await asyncio.wait_for(
                asyncio.to_thread(run, candidate_ids, job),
                timeout=JOB_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("%s batch timed out for source %d", kind, job.source_id)
            self._mark_jobs_failed(all_jobs, "timeout")
            return
        except CancelledByUserError:
            # Primary job was cancelled — let outer handler log it.
            # Extra batch jobs are already RUNNING and will be caught
            # by reconciliation on next restart if not cleaned up.
            raise
        except (PermanentAIError, PermanentMediaError) as exc:
            logger.warning("%s batch permanent error: %s", kind, exc)
            self._mark_jobs_failed(all_jobs, str(exc))
            return
        except Exception as exc:
            logger.exception("%s batch unexpected error", kind)
            self._mark_jobs_failed(all_jobs, f"{type(exc).__name__}: {exc}")
            return

        self._delete_jobs(all_jobs)

    def _run_meaning_batch(self, candidate_ids: list[int], primary_job: Job) -> None:
        """Sync meaning generation — runs in a thread."""
        with self._container.session_scope() as session:
            self._check_not_cancelled(primary_job, session)
            use_case = self._container.meaning_generation_use_case(session)
            use_case.execute_batch(candidate_ids)

    def _run_polish_batch(self, candidate_ids: list[int], primary_job: Job) -> None:
        """Sync phrase polishing — runs in a thread."""
        with self._container.session_scope() as session:
            self._check_not_cancelled(primary_job, session)
            use_case = self._container.phrase_polish_use_case(session)
            use_case.execute_batch(candidate_ids)

    @staticmethod
    def _check_not_cancelled(job: Job, session: Session) -> None:
        from backend.infrastructure.queue.cancellation_token import CancellationToken

        assert job.id is not None
        CancellationToken(job_id=job.id, job_repo=SqlaJobRepository(session)).check()

    async def _handle_media(self, job: Job) -> None:
        """Single-candidate media extraction."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._run_media, job),
                timeout=JOB_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Media extraction timed out for job %d", job.id)
            self._mark_jobs_failed([job], "timeout")
            return
        # Other exceptions bubble up to _process_one_job
        self._delete_jobs([job])

    def _run_media(self, job: Job) -> None:
        """Sync media extraction — runs in a thread."""
        assert job.candidate_id is not None
        with self._container.session_scope() as session:
            use_case = self._container.media_extraction_use_case(session)
            use_case.execute_one(job.candidate_id)

        # Check if all media done → clean up YouTube video
        with self._container.session_scope() as session:
            from backend.infrastructure.persistence.sqla_candidate_repository import (
                SqlaCandidateRepository,
            )
            cand = SqlaCandidateRepository(session).get_by_id(job.candidate_id)
            if cand is not None:
                cleanup = self._container.cleanup_youtube_video_use_case(session)
                cleanup.execute(cand.source_id)

    async def _handle_pronunciation(self, job: Job) -> None:
        """Single-candidate pronunciation download."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._run_pronunciation, job),
                timeout=JOB_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Pronunciation download timed out for job %d", job.id)
            self._mark_jobs_failed([job], "timeout")
            return
        # Other exceptions bubble up to _process_one_job
        self._delete_jobs([job])

    def _run_pronunciation(self, job: Job) -> None:
        """Sync pronunciation download — runs in a thread."""
        assert job.candidate_id is not None
        with self._container.session_scope() as session:
            use_case = self._container.download_pronunciation_use_case(session)
            use_case.execute_one(job.candidate_id)

    async def _handle_topic_targets(self, job: Job) -> None:
        """AI step of a topic source. Processing stays a separate, offline step."""
        await asyncio.wait_for(
            asyncio.to_thread(self._run_topic_targets, job),
            timeout=JOB_TIMEOUT,
        )

    def _run_topic_targets(self, job: Job) -> None:
        """Sync topic target generation — runs in a thread."""
        with self._container.session_scope() as session:
            use_case = self._container.generate_topic_targets_use_case(session)
            use_case.execute(job.source_id)

    async def _handle_tts(self, job: Job) -> None:
        """Hand the claimed TTS job to a subprocess.

        The subprocess loads PyTorch/kokoro, processes this job and every TTS
        job that reaches the head of the queue after it, then exits — freeing
        all TTS memory.
        """
        assert job.id is not None
        logger.info("Spawning TTS subprocess")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "backend.infrastructure.queue.tts_subprocess",
            str(job.id),
        )
        await proc.wait()
        if proc.returncode != 0:
            logger.error("TTS subprocess exited with code %d", proc.returncode)
        else:
            logger.info("TTS subprocess finished successfully")

    async def _handle_video_download(self, job: Job) -> None:
        """YouTube video download — special error handling for source status."""
        try:
            with self._container.session_scope() as session:
                use_case = self._container.download_video_use_case(session)
                use_case.execute(job.source_id)
        except Exception as exc:
            logger.exception("Video download error for source %d", job.source_id)
            with self._container.session_scope() as session:
                from backend.domain.value_objects.source_status import SourceStatus
                from backend.infrastructure.persistence.sqla_source_repository import (
                    SqlaSourceRepository,
                )
                SqlaSourceRepository(session).update_status(
                    job.source_id,
                    SourceStatus.ERROR,
                    error_message=f"Video download failed: {exc}",
                )
            raise  # let outer handler mark job as failed
        self._delete_jobs([job])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mark_jobs_failed(self, jobs: list[Job], error: str) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if not job_ids:
            return
        with self._container.session_scope() as session:
            SqlaJobRepository(session).mark_failed_bulk(job_ids, error)

    def _delete_jobs(self, jobs: list[Job]) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if not job_ids:
            return
        with self._container.session_scope() as session:
            SqlaJobRepository(session).delete_bulk(job_ids)


async def main() -> None:
    """Entry point for ``python -m backend.infrastructure.queue.job_worker``."""
    from backend.infrastructure.container import Container
    from backend.infrastructure.logging_setup import configure_logging

    configure_logging("worker")
    container = Container()
    worker = JobWorker(container)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
