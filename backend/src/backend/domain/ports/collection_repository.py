from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.collection import Collection
    from backend.domain.value_objects.source_eviction import SourceEviction


class CollectionRepository(ABC):
    """Port for persisting collections."""

    @abstractmethod
    def create(self, collection: Collection) -> Collection: ...

    @abstractmethod
    def get_by_id(self, collection_id: int) -> Collection | None:
        """Deleted collections too: Undo needs them."""

    @abstractmethod
    def list_all(self, *, include_deleted: bool = False) -> list[Collection]: ...

    @abstractmethod
    def save(self, collections: Sequence[Collection]) -> None:
        """Persist name, parent, position and deletion mark of existing collections."""

    @abstractmethod
    def record_evictions(
        self, collection_id: int, evictions: Sequence[SourceEviction],
    ) -> None: ...

    @abstractmethod
    def take_evictions(self, collection_id: int) -> list[SourceEviction]:
        """Evictions recorded when the collection was deleted; they are forgotten after this."""

    @abstractmethod
    def rename(self, collection_id: int, new_name: str) -> Collection: ...

    @abstractmethod
    def delete(self, collection_id: int) -> None: ...
