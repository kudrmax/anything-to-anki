from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.media_extraction_job import MediaExtractionJob


class MediaExtractionJobRepository(ABC):
    """Port for persisting media extraction jobs."""

    @abstractmethod
    def create(self, job: MediaExtractionJob) -> MediaExtractionJob: ...

    @abstractmethod
    def get_by_id(self, job_id: int) -> MediaExtractionJob | None: ...

    @abstractmethod
    def get_running(self) -> MediaExtractionJob | None: ...

    @abstractmethod
    def update(self, job: MediaExtractionJob) -> None: ...
