from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import CollectionDTO, collection_to_dto
from backend.domain.entities.collection import Collection
from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository


class CreateCollectionUseCase:
    """Creates a collection, or a subcollection of a top-level one, at the end of its siblings."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(self, name: str, parent_id: int | None = None) -> CollectionDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        tree.check_parent(parent_id)
        clean = tree.check_name(name, parent_id)
        created = self._collection_repo.create(
            Collection(name=clean, parent_id=parent_id, position=tree.next_position(parent_id)),
        )
        return collection_to_dto(created)
