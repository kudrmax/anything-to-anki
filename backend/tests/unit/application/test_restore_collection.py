from __future__ import annotations

import pytest
from backend.application.use_cases.create_collection import CreateCollectionUseCase
from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
from backend.application.use_cases.restore_collection import RestoreCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import CollectionNameExistsError, CollectionNotFoundError
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def source(source_id: int, collection_id: int | None) -> Source:
    return Source(
        id=source_id, status=SourceStatus.NEW, title=f"s{source_id}", collection_id=collection_id,
    )


@pytest.mark.unit
class TestRestoreCollection:
    def setup_method(self) -> None:
        self.collections = InMemoryCollectionRepository([
            Collection(id=1, name="Friends"),
            Collection(id=2, name="Season 1", parent_id=1),
            Collection(id=3, name="IELTS", position=1),
        ])
        self.sources = InMemorySourceRepository([source(10, 1), source(11, 2)])
        DeleteCollectionUseCase(self.collections, self.sources).execute(1)
        self.restore = RestoreCollectionUseCase(self.collections, self.sources)

    def test_puts_everything_back(self) -> None:
        restored = self.restore.execute(1)
        assert restored.name == "Friends"
        assert self.collections.items[1].deleted_at is None
        assert self.collections.items[2].deleted_at is None
        assert self.sources.items[10].collection_id == 1
        assert self.sources.items[11].collection_id == 2

    def test_restore_leaves_sources_moved_by_hand(self) -> None:
        self.sources.set_collections({11: 3})
        self.restore.execute(1)
        assert self.sources.items[11].collection_id == 3
        assert self.sources.items[10].collection_id == 1

    def test_restore_refuses_when_name_taken(self) -> None:
        CreateCollectionUseCase(self.collections).execute("friends")
        with pytest.raises(CollectionNameExistsError):
            self.restore.execute(1)
        assert self.collections.items[1].deleted_at is not None
        assert self.sources.items[10].collection_id is None

    def test_live_collection_cannot_be_restored(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            self.restore.execute(3)
