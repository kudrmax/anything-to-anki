from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.domain.value_objects.job_type import JobType


class JobRepository(ABC):
    """Port for the job queue backed by SQLite."""

    @abstractmethod
    def create_bulk(self, jobs: list[Job]) -> list[Job]:
        """Insert jobs into the queue. Returns jobs with assigned IDs."""

    @abstractmethod
    def dequeue_next(self) -> Job | None:
        """Atomically pick the oldest QUEUED job and mark it RUNNING.
        Returns None if queue is empty."""

    @abstractmethod
    def dequeue_batch(
        self, job_type: JobType, source_id: int, limit: int,
    ) -> list[Job]:
        """Atomically dequeue up to `limit` additional QUEUED jobs
        of the given type and source. Used for meaning batching."""

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
        self, source_id: int,
    ) -> dict[str, dict[str, int]]:
        """Return {job_type: {status: count}} for the given source.
        Used by queue-summary endpoint."""

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
