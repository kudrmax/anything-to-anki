from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import RenamedCollectionDTO
from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository


class RenameCollectionUseCase:
    """Renames a collection; the previous name comes back for Undo."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(self, collection_id: int, new_name: str) -> RenamedCollectionDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        node = tree.get(collection_id)
        clean = tree.check_name(new_name, node.parent_id, exclude_id=collection_id)
        self._collection_repo.save([replace(node, name=clean)])
        return RenamedCollectionDTO(id=collection_id, name=clean, previous_name=node.name)
