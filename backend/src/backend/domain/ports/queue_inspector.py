from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.queued_job_info import QueuedJobInfo


class QueueInspectorPort(ABC):
    """Abstraction for inspecting the arq job queue."""

    @abstractmethod
    async def get_queued_jobs(
        self,
        source_id: int | None = None,
        limit: int = 50,
    ) -> list[QueuedJobInfo]:
        """Return queued jobs ordered by FIFO position."""

    @abstractmethod
    async def get_running_jobs(
        self,
        source_id: int | None = None,
    ) -> list[QueuedJobInfo]:
        """Return currently running jobs."""

    @abstractmethod
    async def get_total_queued(self) -> int:
        """Return total number of queued jobs (unfiltered)."""

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job by ID. Returns True if cancelled."""

    @abstractmethod
    async def cancel_jobs_by_type(
        self,
        job_type: str,
        source_id: int | None = None,
    ) -> int:
        """Cancel all queued jobs of a given type. Returns count cancelled."""
