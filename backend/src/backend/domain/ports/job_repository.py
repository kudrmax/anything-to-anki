from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.job_status import JobStatus
    from backend.domain.value_objects.job_type import JobType

DEFAULT_RUN_LIMIT: int = 1


class JobRepository(ABC):
    """Port for the job queue backed by SQLite."""

    @abstractmethod
    def create_bulk(self, jobs: list[Job]) -> list[Job]:
        """Insert jobs into the queue. Returns jobs with assigned IDs."""

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
    def mark_failed(self, job_id: int, error: str) -> None:
        """Set job status to FAILED with error message."""

    @abstractmethod
    def mark_failed_bulk(self, job_ids: list[int], error: str) -> None:
        """Bulk FAILED for a list of job IDs."""

    @abstractmethod
    def delete(self, job_id: int) -> None:
        """Remove a completed or cancelled job from the queue."""

    @abstractmethod
    def delete_bulk(self, job_ids: list[int]) -> None:
        """Remove multiple jobs from the queue."""

    @abstractmethod
    def delete_by_source_and_type(
        self, source_id: int, job_type: JobType,
    ) -> int:
        """Delete all QUEUED and RUNNING jobs for source+type. Returns count.
        Used by cancel endpoint."""

    @abstractmethod
    def delete_failed_by_source_and_type(
        self, source_id: int, job_type: JobType,
    ) -> list[Job]:
        """Delete FAILED jobs for source+type, returning them before deletion.
        Used by retry endpoint to know which candidates to re-enqueue."""

    @abstractmethod
    def fail_all_running(self, error: str) -> int:
        """Mark all RUNNING jobs as FAILED. Used by worker startup reconciliation.
        Returns count of affected rows."""

    @abstractmethod
    def get(self, job_id: int) -> Job | None:
        """Return the job, or None if it no longer exists."""

    @abstractmethod
    def job_exists(self, job_id: int) -> bool:
        """Check if a job still exists. Used by CancellationToken."""

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
    def get_source_ids_with_active_jobs(
        self, job_type: JobType,
    ) -> list[int]:
        """Return distinct source IDs that have QUEUED or RUNNING jobs of the given type."""

    @abstractmethod
    def get_jobs_by_status(
        self,
        statuses: list[JobStatus],
        source_id: int | None = None,
        job_type: JobType | None = None,
        limit: int | None = None,
    ) -> list[Job]:
        """Return jobs matching given statuses, ordered by created_at asc.
        Used by queue management page to list active/queued jobs."""

    @abstractmethod
    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
        job_type: JobType | None = None,
    ) -> list[dict[str, Any]]:
        """Return failed jobs grouped by (job_type, error).
        Each dict: {job_type, error, count, source_ids, source_counts, candidate_ids};
        source_counts maps source id to its number of failed jobs in the group.
        Used by queue management page."""
