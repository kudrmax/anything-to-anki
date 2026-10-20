from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import CollectionDTO, collection_to_dto
from backend.domain.exceptions import CollectionNotFoundError
from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from backend.domain.entities.collection import Collection
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork


class RestoreCollectionUseCase:
    """Undo of a delete: the collection, its subtree deleted with it and the sources come back.
    A source the user has moved since stays where they put it."""

    def __init__(
        self, collection_repo: CollectionRepository, source_repo: SourceRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._collection_repo = collection_repo
        self._source_repo = source_repo

    def execute(self, collection_id: int) -> CollectionDTO:
        with self._unit_of_work.write():
            return self._restore(collection_id)

    def _restore(self, collection_id: int) -> CollectionDTO:
        node = self._collection_repo.get_by_id(collection_id)
        if node is None or node.deleted_at is None:
            raise CollectionNotFoundError(collection_id)
        live = self._collection_repo.list_all()
        tree = CollectionTree(live)
        tree.check_parent(node.parent_id)
        tree.check_name(node.name, node.parent_id)

        revived = [replace(c, deleted_at=None) for c in [node, *self._deleted_with(node)]]
        CollectionTree([*live, *revived]).check_fits(collection_id)
        self._collection_repo.save(revived)

        where_now = {s.id: s.collection_id for s in self._source_repo.list_all()}
        back = {
            e.source_id: e.previous_collection_id
            for e in self._collection_repo.take_evictions(collection_id)
            if e.source_id in where_now and where_now[e.source_id] == e.moved_to_collection_id
        }
        self._source_repo.set_collections(back)
        return collection_to_dto(revived[0])

    def _deleted_with(self, node: Collection) -> list[Collection]:
        """Descendants of `node` deleted in the same operation, at any depth."""
        same_stamp = [
            c for c in self._collection_repo.list_all(include_deleted=True)
            if c.deleted_at == node.deleted_at and c.id != node.id
        ]
        found: list[Collection] = []
        frontier = {node.id}
        while frontier:
            level = [c for c in same_stamp if c.parent_id in frontier and c not in found]
            found += level
            frontier = {c.id for c in level}
        return found
