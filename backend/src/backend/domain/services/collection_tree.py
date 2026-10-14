from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    CollectionMoveNotAllowedError,
    CollectionNameExistsError,
    CollectionNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.collection import Collection

MAX_NAME_LENGTH = 200


class CollectionTree:
    """Live (not deleted) collections as a tree of two levels: collection → subcollection."""

    def __init__(self, collections: Iterable[Collection]) -> None:
        self._by_id: dict[int, Collection] = {
            c.id: c for c in collections if c.id is not None and c.deleted_at is None
        }

    def get(self, collection_id: int) -> Collection:
        found = self._by_id.get(collection_id)
        if found is None:
            raise CollectionNotFoundError(collection_id)
        return found

    def has(self, collection_id: int) -> bool:
        return collection_id in self._by_id

    def children(self, parent_id: int | None) -> list[Collection]:
        return sorted(
            (c for c in self._by_id.values() if c.parent_id == parent_id),
            key=lambda c: (c.position, c.id or 0),
        )

    def subtree_ids(self, collection_id: int) -> set[int]:
        self.get(collection_id)
        return {collection_id, *(c.id for c in self.children(collection_id) if c.id is not None)}

    def path(self, collection_id: int) -> list[str]:
        node = self.get(collection_id)
        if node.parent_id is None:
            return [node.name]
        return [self.get(node.parent_id).name, node.name]

    def next_position(self, parent_id: int | None) -> int:
        siblings = self.children(parent_id)
        return siblings[-1].position + 1 if siblings else 0

    def find_top_level(self, name: str) -> Collection | None:
        key = name.strip().casefold()
        return next((c for c in self.children(None) if c.name.casefold() == key), None)

    def index_of(self, collection_id: int) -> int:
        node = self.get(collection_id)
        return [c.id for c in self.children(node.parent_id)].index(collection_id)

    def check_name(
        self,
        name: str,
        parent_id: int | None,
        *,
        exclude_id: int | None = None,
    ) -> str:
        """The trimmed name, if it is valid and free among the children of `parent_id`."""
        clean = name.strip()
        if not clean:
            raise ValueError("Collection name must not be empty")
        if len(clean) > MAX_NAME_LENGTH:
            raise ValueError(f"Collection name must not exceed {MAX_NAME_LENGTH} characters")
        key = clean.casefold()
        if any(c.name.casefold() == key and c.id != exclude_id for c in self.children(parent_id)):
            raise CollectionNameExistsError(clean)
        return clean

    def check_parent(self, parent_id: int | None) -> None:
        if parent_id is not None and not self.get(parent_id).is_top_level:
            raise CollectionMoveNotAllowedError("A subcollection can't hold collections")

    def place(self, collection_id: int, parent_id: int | None, position: int) -> list[Collection]:
        """Collections whose parent or position change when `collection_id` lands at `position`
        among the children of `parent_id` (the index counts siblings without the moved one)."""
        node = self.get(collection_id)
        self._check_move(node, parent_id)
        siblings = [c for c in self.children(parent_id) if c.id != collection_id]
        index = max(0, min(position, len(siblings)))
        siblings.insert(index, replace(node, parent_id=parent_id))
        changed = self._renumbered(siblings)
        if node.parent_id != parent_id:
            left = [c for c in self.children(node.parent_id) if c.id != collection_id]
            changed += self._renumbered(left)
        return changed

    def _renumbered(self, ordered: list[Collection]) -> list[Collection]:
        changed: list[Collection] = []
        for index, collection in enumerate(ordered):
            updated = replace(collection, position=index)
            assert updated.id is not None
            if updated != self._by_id[updated.id]:
                changed.append(updated)
        return changed

    def _check_move(self, node: Collection, parent_id: int | None) -> None:
        assert node.id is not None
        if parent_id is not None:
            if parent_id == node.id:
                raise CollectionMoveNotAllowedError("A collection can't go inside itself")
            self.check_parent(parent_id)
            if self.children(node.id):
                raise CollectionMoveNotAllowedError(
                    "A collection with subcollections stays at the top level",
                )
        if node.parent_id != parent_id:
            self.check_name(node.name, parent_id, exclude_id=node.id)
