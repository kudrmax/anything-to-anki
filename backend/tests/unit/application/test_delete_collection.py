from __future__ import annotations

import pytest
from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import CollectionNotFoundError
from backend.domain.value_objects.source_eviction import SourceEviction
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def source(source_id: int, collection_id: int | None) -> Source:
    return Source(
        id=source_id, status=SourceStatus.NEW, title=f"s{source_id}", collection_id=collection_id,
    )


@pytest.mark.unit
class TestDeleteCollection:
    def setup_method(self) -> None:
        self.collections = InMemoryCollectionRepository([
            Collection(id=1, name="Friends"),
            Collection(id=2, name="Season 1", parent_id=1),
            Collection(id=3, name="IELTS", position=1),
        ])
        self.sources = InMemorySourceRepository([source(10, 1), source(11, 2), source(12, 3)])
        self.use_case = DeleteCollectionUseCase(self.collections, self.sources)

    def test_collection_sends_whole_subtree_to_unsorted(self) -> None:
        deleted = self.use_case.execute(1)
        assert (deleted.name, deleted.evicted_source_count) == ("Friends", 2)
        assert self.sources.items[10].collection_id is None
        assert self.sources.items[11].collection_id is None
        assert self.sources.items[12].collection_id == 3
        assert self.collections.items[1].deleted_at is not None
        assert self.collections.items[2].deleted_at == self.collections.items[1].deleted_at
        assert set(self.collections.evictions[1]) == {
            SourceEviction(10, 1, None), SourceEviction(11, 2, None),
        }

    def test_subcollection_hands_sources_to_parent(self) -> None:
        self.use_case.execute(2)
        assert self.sources.items[11].collection_id == 1
        assert self.collections.items[1].deleted_at is None

    def test_not_found(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            self.use_case.execute(99)
