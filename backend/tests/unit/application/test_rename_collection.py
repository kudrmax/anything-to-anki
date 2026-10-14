from __future__ import annotations

import pytest
from backend.application.use_cases.rename_collection import RenameCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNameExistsError, CollectionNotFoundError

from tests.unit.application.collection_fakes import InMemoryCollectionRepository


@pytest.mark.unit
class TestRenameCollection:
    def setup_method(self) -> None:
        self.repo = InMemoryCollectionRepository([
            Collection(id=1, name="Friends"),
            Collection(id=2, name="Lost", position=1),
        ])

    def test_returns_previous_name_for_undo(self) -> None:
        renamed = RenameCollectionUseCase(self.repo).execute(1, " Friends (US) ")
        assert (renamed.name, renamed.previous_name) == ("Friends (US)", "Friends")
        assert self.repo.items[1].name == "Friends (US)"

    def test_case_change_of_own_name(self) -> None:
        assert RenameCollectionUseCase(self.repo).execute(1, "FRIENDS").name == "FRIENDS"

    def test_sibling_name_taken(self) -> None:
        with pytest.raises(CollectionNameExistsError):
            RenameCollectionUseCase(self.repo).execute(1, "lost")

    def test_not_found(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            RenameCollectionUseCase(self.repo).execute(9, "X")
