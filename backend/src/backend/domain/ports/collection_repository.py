from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.collection import Collection


class CollectionRepository(ABC):
    """Port for persisting collections."""

    @abstractmethod
    def create(self, collection: Collection) -> Collection: ...

    @abstractmethod
    def get_by_id(self, collection_id: int) -> Collection | None: ...

    @abstractmethod
    def list_all(self) -> list[Collection]: ...

    @abstractmethod
    def rename(self, collection_id: int, new_name: str) -> Collection: ...

    @abstractmethod
    def delete(self, collection_id: int) -> None: ...
