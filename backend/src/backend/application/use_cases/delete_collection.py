from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import DeletedCollectionDTO
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.value_objects.source_eviction import SourceEviction

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork


class DeleteCollectionUseCase:
    """Deletes a collection softly with its whole subtree, keeping the sources: they go to the
    parent of the deleted collection (Unsorted for a top-level one). Where they lay is kept
    for Undo."""

    def __init__(
        self, collection_repo: CollectionRepository, source_repo: SourceRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._collection_repo = collection_repo
        self._source_repo = source_repo

    def execute(self, collection_id: int) -> DeletedCollectionDTO:
        with self._unit_of_work.write():
            return self._delete(collection_id)

    def _delete(self, collection_id: int) -> DeletedCollectionDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        node = tree.get(collection_id)
        subtree = tree.subtree_ids(collection_id)
        target = node.parent_id
        evictions = [
            SourceEviction(s.id, s.collection_id, target)
            for s in self._source_repo.list_all()
            if s.id is not None and s.collection_id is not None and s.collection_id in subtree
        ]
        self._source_repo.set_collections({e.source_id: target for e in evictions})
        self._collection_repo.record_evictions(collection_id, evictions)
        now = datetime.now(tz=UTC)
        doomed = [tree.get(i) for i in subtree]
        self._collection_repo.save([replace(c, deleted_at=now) for c in doomed])
        return DeletedCollectionDTO(
            id=collection_id, name=node.name, evicted_source_count=len(evictions),
        )
