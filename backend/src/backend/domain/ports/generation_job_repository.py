from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.generation_job import GenerationJob


class GenerationJobRepository(ABC):
    """Port for persisting generation jobs."""

    @abstractmethod
    def create(self, job: GenerationJob) -> GenerationJob: ...

    @abstractmethod
    def get_by_id(self, job_id: int) -> GenerationJob | None: ...

    @abstractmethod
    def get_running(self) -> GenerationJob | None: ...

    @abstractmethod
    def get_pending(self) -> list[GenerationJob]: ...

    @abstractmethod
    def get_next_pending(self, source_id: int | None) -> GenerationJob | None:
        """Get the next pending job for the given source (or any source if None), ordered by
        created_at.
        """

    @abstractmethod
    def cancel_pending_for_source(self, source_id: int | None) -> None:
        """Cancel all pending jobs for the given source (or for all sources if None)."""

    @abstractmethod
    def update(self, job: GenerationJob) -> None: ...
