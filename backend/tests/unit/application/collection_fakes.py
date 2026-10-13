from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.ports.collection_repository import CollectionRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.collection import Collection
    from backend.domain.value_objects.source_eviction import SourceEviction


class InMemoryCollectionRepository(CollectionRepository):
    """Port fake: keeps collections and evictions in dicts."""

    def __init__(self, collections: Sequence[Collection] = ()) -> None:
        self.items: dict[int, Collection] = {c.id: c for c in collections if c.id is not None}
        self.evictions: dict[int, list[SourceEviction]] = {}

    def create(self, collection: Collection) -> Collection:
        created = replace(collection, id=max(self.items, default=0) + 1)
        self.items[created.id] = created  # type: ignore[index]
        return created

    def get_by_id(self, collection_id: int) -> Collection | None:
        return self.items.get(collection_id)

    def list_all(self, *, include_deleted: bool = False) -> list[Collection]:
        return [c for c in self.items.values() if include_deleted or c.deleted_at is None]

    def save(self, collections: Sequence[Collection]) -> None:
        for collection in collections:
            self.items[collection.id] = collection  # type: ignore[index]

    def record_evictions(self, collection_id: int, evictions: Sequence[SourceEviction]) -> None:
        self.evictions.setdefault(collection_id, []).extend(evictions)

    def take_evictions(self, collection_id: int) -> list[SourceEviction]:
        return self.evictions.pop(collection_id, [])

    def delete(self, collection_id: int) -> None:
        self.items.pop(collection_id, None)
