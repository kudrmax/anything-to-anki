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
MAX_DEPTH = 5


class CollectionTree:
    """Live (not deleted) collections as a tree no deeper than `max_depth` levels."""

    def __init__(
        self, collections: Iterable[Collection], *, max_depth: int = MAX_DEPTH,
    ) -> None:
        self._by_id: dict[int, Collection] = {
            c.id: c for c in collections if c.id is not None and c.deleted_at is None
        }
        self._max_depth = max_depth

    @property
    def max_depth(self) -> int:
        return self._max_depth

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

    def ancestors(self, collection_id: int) -> list[Collection]:
        """Root first, parent last."""
        chain: list[Collection] = []
        seen = {collection_id}
        parent_id = self.get(collection_id).parent_id
        while parent_id is not None and parent_id in self._by_id and parent_id not in seen:
            seen.add(parent_id)
            parent = self._by_id[parent_id]
            chain.append(parent)
            parent_id = parent.parent_id
        return chain[::-1]

    def depth(self, collection_id: int) -> int:
        """Top level is 1."""
        return len(self.ancestors(collection_id)) + 1

    def height(self, collection_id: int) -> int:
        """A leaf is 1."""
        self.get(collection_id)
        height = 0
        level = {collection_id}
        seen: set[int] = set()
        while level:
            height += 1
            seen |= level
            level = {
                c.id for parent in level for c in self.children(parent)
                if c.id is not None and c.id not in seen
            }
        return height

    def descendant_ids(self, collection_id: int) -> set[int]:
        self.get(collection_id)
        found: set[int] = set()
        stack = [collection_id]
        while stack:
            for child in self.children(stack.pop()):
                if child.id is not None and child.id not in found and child.id != collection_id:
                    found.add(child.id)
                    stack.append(child.id)
        return found

    def subtree_ids(self, collection_id: int) -> set[int]:
        return {collection_id, *self.descendant_ids(collection_id)}

    def path(self, collection_id: int) -> list[str]:
        node = self.get(collection_id)
        return [*(c.name for c in self.ancestors(collection_id)), node.name]

    def can_hold_children(self, collection_id: int) -> bool:
        return self.depth(collection_id) < self._max_depth

    def move_targets(self, collection_id: int) -> list[int | None]:
        """Every parent `collection_id` may move under, `None` being the top level; tree order."""
        own = self.subtree_ids(collection_id)
        room = self._max_depth - self.height(collection_id)
        return [None, *(
            parent_id for parent_id in self._tree_order()
            if parent_id not in own and self.depth(parent_id) <= room
        )]

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
        if parent_id is not None and not self.can_hold_children(parent_id):
            raise self._too_deep()

    def check_fits(self, collection_id: int) -> None:
        """`collection_id` with its whole subtree stays within the depth limit."""
        if self.depth(collection_id) + self.height(collection_id) - 1 > self._max_depth:
            raise self._too_deep()

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

    def _tree_order(self) -> list[int]:
        ordered: list[int] = []
        seen: set[int] = set()
        stack = [c.id for c in reversed(self.children(None)) if c.id is not None]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            ordered.append(current)
            stack.extend(c.id for c in reversed(self.children(current)) if c.id is not None)
        return ordered

    def _too_deep(self) -> CollectionMoveNotAllowedError:
        return CollectionMoveNotAllowedError(
            f"Collections can't be nested deeper than {self._max_depth} levels",
        )

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
            self.get(parent_id)
            if parent_id == node.id:
                raise CollectionMoveNotAllowedError("A collection can't go inside itself")
            if parent_id in self.descendant_ids(node.id):
                raise CollectionMoveNotAllowedError(
                    "A collection can't go inside its own subcollection",
                )
            if self.depth(parent_id) + self.height(node.id) > self._max_depth:
                raise self._too_deep()
        if node.parent_id != parent_id:
            self.check_name(node.name, parent_id, exclude_id=node.id)
