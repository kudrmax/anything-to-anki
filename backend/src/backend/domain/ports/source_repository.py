from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
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
    ) -> None: ...
