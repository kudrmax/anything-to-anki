"""SQLite-backed async job worker.

Replaces arq+Redis. Polls the jobs table for QUEUED work,
dispatches to handlers, manages lifecycle (done→delete, fail→mark).

Run with: python -m backend.infrastructure.queue.job_worker
"""
from __future__ import annotations

import asyncio
import logging
import signal
from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError, PermanentAIError, PermanentMediaError
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

POLL_DELAY: float = 0.1  # seconds between polls when queue is empty
JOB_TIMEOUT: int = 600  # seconds per job (10 minutes)
MEANING_BATCH_SIZE: int = 15


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
            job = job_repo.dequeue_next()

        if job is None:
            return False

        logger.info(
            "Processing job %d: type=%s candidate=%s source=%d",
            job.id, job.job_type.value, job.candidate_id, job.source_id,
        )

        try:
            match job.job_type:
                case JobType.MEANING:
                    # Meaning handler manages its own batch success/failure
                    await self._handle_meaning(job)
                    return True
                case JobType.MEDIA:
                    await self._handle_media(job)
                case JobType.PRONUNCIATION:
                    await self._handle_pronunciation(job)
                case JobType.VIDEO_DOWNLOAD:
                    await self._handle_video_download(job)
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

    async def _handle_meaning(self, job: Job) -> None:
        """Meaning generation with opportunistic batching.

        Dequeues extra QUEUED meaning jobs for the same source,
        processes them all in one batch. Manages its own success/failure
        because the outer handler only knows about the primary job.
        """
        with self._container.session_scope() as session:
            extra_jobs = SqlaJobRepository(session).dequeue_batch(
                JobType.MEANING, job.source_id, limit=MEANING_BATCH_SIZE - 1,
            )
        all_jobs = [job, *extra_jobs]
        candidate_ids = [j.candidate_id for j in all_jobs if j.candidate_id is not None]

        if not candidate_ids:
            self._delete_jobs(all_jobs)
            return

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._run_meaning_batch, candidate_ids, job),
                timeout=JOB_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Meaning batch timed out for source %d", job.source_id)
            self._mark_jobs_failed(all_jobs, "timeout")
            return
        except CancelledByUserError:
            # Primary job was cancelled — let outer handler log it.
            # Extra batch jobs are already RUNNING and will be caught
            # by reconciliation on next restart if not cleaned up.
            raise
        except (PermanentAIError, PermanentMediaError) as exc:
            logger.warning("Meaning batch permanent error: %s", exc)
            self._mark_jobs_failed(all_jobs, str(exc))
            return
        except Exception as exc:
            logger.exception("Meaning batch unexpected error")
            self._mark_jobs_failed(all_jobs, f"{type(exc).__name__}: {exc}")
            return

        self._delete_jobs(all_jobs)

    def _run_meaning_batch(self, candidate_ids: list[int], primary_job: Job) -> None:
        """Sync meaning generation — runs in a thread."""
        assert primary_job.id is not None
        with self._container.session_scope() as session:
            from backend.infrastructure.queue.cancellation_token import CancellationToken

            token = CancellationToken(
                job_id=primary_job.id,
                job_repo=SqlaJobRepository(session),
            )
            token.check()
            use_case = self._container.meaning_generation_use_case(session)
            use_case.execute_batch(candidate_ids)

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
