from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.failed_job_group import FailedJobGroup
    from backend.domain.value_objects.job_selection import JobSelection
    from backend.domain.value_objects.job_status import JobStatus
    from backend.domain.value_objects.job_type import JobType

DEFAULT_RUN_LIMIT: int = 1


class JobRepository(ABC):
    """Port for the job queue backed by SQLite.

    A job is identified by its key: (job_type, candidate_id) for candidate jobs,
    (job_type, source_id) for source-level jobs. The queue holds at most one
    active (QUEUED or RUNNING) job per key, and a failed job stays only until
    the same work is queued again or succeeds.
    """

    # ── Lifecycle ────────────────────────────────────────────────────

    @abstractmethod
    def enqueue(self, jobs: list[Job]) -> list[Job]:
        """Queue jobs at the tail. Jobs whose key is already active are skipped;
        failed jobs with the same key are superseded. Returns the queued jobs."""

    @abstractmethod
    def claim_next_run(
        self,
        run_limits: Mapping[JobType, int],
        accepted_types: frozenset[JobType] | None = None,
    ) -> list[Job]:
        """Atomically claim the head of the queue and mark it RUNNING.

        The queue is strictly FIFO across all job types. The run is the oldest
        QUEUED job plus the jobs immediately following it that share its type
        and source, capped by ``run_limits`` (DEFAULT_RUN_LIMIT for absent types).
        A run never skips over an older job, so batching cannot reorder work.

        If ``accepted_types`` is given and the head is of another type, nothing
        is claimed. Returns an empty list when nothing was claimed."""

    @abstractmethod
    def still_claimed(self, jobs: list[Job]) -> set[int]:
        """Ids of the claimed ``jobs`` still RUNNING under that same claim.

        A job cancelled or failed by timeout meanwhile is no longer RUNNING, and
        its result must be dropped. The claim is matched by ``started_at`` too:
        a job retried and claimed again, or a new job that reused the id, is a
        different claim."""

    @abstractmethod
    def complete(self, jobs: list[Job]) -> None:
        """Remove finished jobs together with failed jobs of the same keys."""

    @abstractmethod
    def fail(self, job_ids: list[int], error: str) -> None:
        """Mark RUNNING jobs FAILED. Jobs cancelled meanwhile stay gone."""

    @abstractmethod
    def requeue_running(self) -> int:
        """Return every RUNNING job to QUEUED in its original place.
        Used when the worker starts: whatever was running was interrupted."""

    @abstractmethod
    def fail_running(self, job_type: JobType, error: str) -> int:
        """Mark every RUNNING job of the type FAILED. Returns how many."""

    # ── User actions ─────────────────────────────────────────────────

    @abstractmethod
    def cancel(self, selection: JobSelection) -> int:
        """Remove the selected QUEUED and RUNNING jobs. Returns how many."""

    @abstractmethod
    def dismiss(self, selection: JobSelection) -> int:
        """Remove the selected FAILED jobs. Returns how many."""

    @abstractmethod
    def retry(self, selection: JobSelection) -> int:
        """Queue the selected FAILED jobs again at the tail. A failed job whose
        key is already active is dropped instead. Returns how many were queued."""

    # ── Reads ────────────────────────────────────────────────────────

    @abstractmethod
    def get(self, job_id: int) -> Job | None:
        """Return the job, or None if it no longer exists."""

    @abstractmethod
    def has_active_jobs_for_source(
        self, source_id: int, job_types: frozenset[JobType] | None = None,
    ) -> bool:
        """True if source has any QUEUED or RUNNING jobs.
        Optionally filter by job types."""

    @abstractmethod
    def get_queue_summary(
        self, source_id: int | None = None,
    ) -> dict[str, dict[str, int]]:
        """Return {job_type: {status: count}}.
        If source_id is None, returns global counts."""

    @abstractmethod
    def get_jobs_for_candidates(
        self, candidate_ids: list[int],
    ) -> dict[int, dict[str, Job]]:
        """Return {candidate_id: {job_type_value: Job}} for jobs matching the given candidates.
        Used by DTO construction to derive enrichment status.
        When multiple jobs exist for the same candidate+type, active (queued/running)
        takes precedence over failed."""

    @abstractmethod
    def get_jobs_by_status(
        self,
        statuses: list[JobStatus],
        source_id: int | None = None,
        job_type: JobType | None = None,
        limit: int | None = None,
    ) -> list[Job]:
        """Return jobs matching given statuses, in queue order."""

    @abstractmethod
    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
        job_type: JobType | None = None,
    ) -> list[FailedJobGroup]:
        """Return failed jobs grouped by (job_type, error), largest group first."""
