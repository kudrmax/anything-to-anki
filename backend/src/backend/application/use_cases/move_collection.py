from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import MovedCollectionDTO
from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository


class MoveCollectionUseCase:
    """Reorders a collection among its siblings or moves it to another parent; the previous place
    comes back for Undo."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(
        self, collection_id: int, parent_id: int | None, position: int,
    ) -> MovedCollectionDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        node = tree.get(collection_id)
        previous_position = tree.index_of(collection_id)
        self._collection_repo.save(tree.place(collection_id, parent_id, position))
        return MovedCollectionDTO(
            id=collection_id,
            previous_parent_id=node.parent_id,
            previous_position=previous_position,
        )
