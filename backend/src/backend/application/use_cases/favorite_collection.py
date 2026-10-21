from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.unit_of_work import UnitOfWork


class FavoriteCollectionUseCase:
    """Adds a collection to favorites or takes it out; adding it again keeps its place."""

    def __init__(self, collection_repo: CollectionRepository, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work
        self._collection_repo = collection_repo

    def execute(self, collection_id: int, *, favorite: bool) -> None:
        with self._unit_of_work.write():
            node = CollectionTree(self._collection_repo.list_all()).get(collection_id)
            if favorite == (node.favorited_at is not None):
                return
            favorited_at = datetime.now(tz=UTC) if favorite else None
            self._collection_repo.save([replace(node, favorited_at=favorited_at)])
