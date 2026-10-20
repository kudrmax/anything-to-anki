from __future__ import annotations

from unittest.mock import MagicMock

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
        created = CreateCollectionUseCase(repo(), MagicMock()).execute("  IELTS ")
        assert (created.name, created.parent_id, created.position) == ("IELTS", None, 1)

    def test_subcollection(self) -> None:
        created = CreateCollectionUseCase(repo(), MagicMock()).execute("Season 2", parent_id=1)
        assert (created.parent_id, created.position) == (1, 1)

    def test_duplicate_among_siblings(self) -> None:
        with pytest.raises(CollectionNameExistsError):
            CreateCollectionUseCase(repo(), MagicMock()).execute("season 1", parent_id=1)

    def test_third_level(self) -> None:
        created = CreateCollectionUseCase(repo(), MagicMock()).execute("Episode", parent_id=2)
        assert created.parent_id == 2

    def test_no_sixth_level(self) -> None:
        use_case = CreateCollectionUseCase(repo(), MagicMock())
        parent_id = 2
        for name in ("L3", "L4", "L5"):
            parent_id = use_case.execute(name, parent_id=parent_id).id
        with pytest.raises(CollectionMoveNotAllowedError):
            use_case.execute("L6", parent_id=parent_id)

    def test_unknown_parent(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            CreateCollectionUseCase(repo(), MagicMock()).execute("X", parent_id=99)
