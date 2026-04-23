from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.rename_collection import RenameCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNameExistsError, CollectionNotFoundError


@pytest.mark.unit
class TestRenameCollectionUseCase:
    def setup_method(self) -> None:
        self.collection_repo = MagicMock()
        self.use_case = RenameCollectionUseCase(collection_repo=self.collection_repo)

    def test_renames_collection(self) -> None:
        self.collection_repo.get_by_id.return_value = Collection(id=1, name="Old Name")
        self.collection_repo.list_all.return_value = [Collection(id=1, name="Old Name")]
        self.collection_repo.rename.return_value = Collection(id=1, name="New Name")
        result = self.use_case.execute(1, "New Name")
        assert result.name == "New Name"
        self.collection_repo.rename.assert_called_once_with(1, "New Name")

    def test_not_found_raises(self) -> None:
        self.collection_repo.get_by_id.return_value = None
        with pytest.raises(CollectionNotFoundError):
            self.use_case.execute(999, "New Name")

    def test_duplicate_name_raises(self) -> None:
        self.collection_repo.get_by_id.return_value = Collection(id=1, name="Old")
        self.collection_repo.list_all.return_value = [
            Collection(id=1, name="Old"),
            Collection(id=2, name="Taken"),
        ]
        with pytest.raises(CollectionNameExistsError):
            self.use_case.execute(1, "Taken")

    def test_same_name_as_self_allowed(self) -> None:
        self.collection_repo.get_by_id.return_value = Collection(id=1, name="Same")
        self.collection_repo.list_all.return_value = [Collection(id=1, name="Same")]
        self.collection_repo.rename.return_value = Collection(id=1, name="Same")
        result = self.use_case.execute(1, "Same")
        assert result.name == "Same"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute(1, "")
