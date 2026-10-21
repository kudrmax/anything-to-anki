from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.document import Document


class DocumentRepository(ABC):
    """Port for persisting the document of a source. A document is written once, with its
    source, and never changes."""

    @abstractmethod
    def save(self, source_id: int, document: Document) -> None:
        """SourceDocumentExistsError when the source has a document already."""

    @abstractmethod
    def get(self, source_id: int) -> Document | None: ...

    @abstractmethod
    def fingerprint(self, source_id: int) -> str | None:
        """A digest of the stored document: two stored documents with the same digest are
        the same document. None for a source without one."""

    @abstractmethod
    def size_hints(self, source_ids: Collection[int]) -> dict[int, int]:
        """Source id → the length of its stored document, a hint of the size of its text;
        a source without a document is left out."""
