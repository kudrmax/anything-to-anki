from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.document import Document


class DocumentRepository(ABC):
    """Port for persisting the document of a source."""

    @abstractmethod
    def save(self, source_id: int, document: Document) -> None: ...

    @abstractmethod
    def get(self, source_id: int) -> Document | None: ...
