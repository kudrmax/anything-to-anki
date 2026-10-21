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
        """What names the stored document: a document is written once, with its source, so
        the source's id with this names one document — a source made later under the same
        id has another fingerprint. Cheap: the document is not read. None for a source
        without one."""

    @abstractmethod
    def size_hints(self, source_ids: Collection[int]) -> dict[int, int]:
        """Source id → the length of its document's text (`Document.text`), read without
        laying the document out; a source without a document is left out."""
