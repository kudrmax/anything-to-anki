from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.favorite_collection import FavoriteCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNotFoundError

from tests.unit.application.collection_fakes import InMemoryCollectionRepository

EARLIER = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.mark.unit
class TestFavoriteCollection:
    def setup_method(self) -> None:
        self.repo = InMemoryCollectionRepository([
            Collection(id=1, name="Friends"),
            Collection(id=2, name="Lost", favorited_at=EARLIER),
            Collection(id=3, name="Gone", deleted_at=EARLIER),
        ])
        self.use_case = FavoriteCollectionUseCase(self.repo, MagicMock())

    def test_adds_with_the_moment_of_adding(self) -> None:
        self.use_case.execute(1, favorite=True)
        assert self.repo.items[1].favorited_at is not None
        assert self.repo.items[1].favorited_at > EARLIER

    def test_adding_again_keeps_its_place(self) -> None:
        self.use_case.execute(2, favorite=True)
        assert self.repo.items[2].favorited_at == EARLIER

    def test_removes(self) -> None:
        self.use_case.execute(2, favorite=False)
        assert self.repo.items[2].favorited_at is None

    def test_deleted_or_unknown_is_not_found(self) -> None:
        for collection_id in (3, 9):
            with pytest.raises(CollectionNotFoundError):
                self.use_case.execute(collection_id, favorite=True)
