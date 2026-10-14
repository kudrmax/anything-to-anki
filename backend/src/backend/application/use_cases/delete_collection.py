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


class DeleteCollectionUseCase:
    """Deletes a collection softly, keeping its sources: a subcollection hands them to its parent,
    a collection sends its whole subtree to Unsorted. Where they lay is kept for Undo."""

    def __init__(
        self, collection_repo: CollectionRepository, source_repo: SourceRepository,
    ) -> None:
        self._collection_repo = collection_repo
        self._source_repo = source_repo

    def execute(self, collection_id: int) -> DeletedCollectionDTO:
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
        doomed = [node, *tree.children(collection_id)]
        self._collection_repo.save([replace(c, deleted_at=now) for c in doomed])
        return DeletedCollectionDTO(
            id=collection_id, name=node.name, evicted_source_count=len(evictions),
        )
