from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


class SourceRepository(ABC):
    """Port for persisting and retrieving text sources."""

    @abstractmethod
    def create(self, source: Source) -> Source: ...

    @abstractmethod
    def get_by_id(self, source_id: int) -> Source | None: ...

    @abstractmethod
    def list_all(self) -> list[Source]: ...

    @abstractmethod
    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        *,
        cleaned_text: str | None = None,
        error_message: str | None = None,
        processing_stage: ProcessingStage | None = None,
    ) -> None: ...

    @abstractmethod
    def update_title(self, source_id: int, title: str) -> None: ...

    @abstractmethod
    def delete(self, source_id: int) -> None: ...
