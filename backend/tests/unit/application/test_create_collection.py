from __future__ import annotations

import pytest
from backend.application.use_cases.create_collection import CreateCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import (
    CollectionMoveNotAllowedError,
    CollectionNameExistsError,
    CollectionNotFoundError,
)

from tests.unit.application.collection_fakes import InMemoryCollectionRepository


def repo() -> InMemoryCollectionRepository:
    return InMemoryCollectionRepository([
        Collection(id=1, name="Friends", position=0),
        Collection(id=2, name="Season 1", parent_id=1, position=0),
    ])


@pytest.mark.unit
class TestCreateCollection:
    def test_top_level_goes_last(self) -> None:
        created = CreateCollectionUseCase(repo()).execute("  IELTS ")
        assert (created.name, created.parent_id, created.position) == ("IELTS", None, 1)

    def test_subcollection(self) -> None:
        created = CreateCollectionUseCase(repo()).execute("Season 2", parent_id=1)
        assert (created.parent_id, created.position) == (1, 1)

    def test_duplicate_among_siblings(self) -> None:
        with pytest.raises(CollectionNameExistsError):
            CreateCollectionUseCase(repo()).execute("season 1", parent_id=1)

    def test_no_third_level(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            CreateCollectionUseCase(repo()).execute("Episode", parent_id=2)

    def test_unknown_parent(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            CreateCollectionUseCase(repo()).execute("X", parent_id=99)
