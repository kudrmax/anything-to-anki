from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.create_collection import CreateCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNameExistsError


@pytest.mark.unit
class TestCreateCollectionUseCase:
    def setup_method(self) -> None:
        self.collection_repo = MagicMock()
        self.use_case = CreateCollectionUseCase(collection_repo=self.collection_repo)

    def test_creates_collection(self) -> None:
        self.collection_repo.list_all.return_value = []
        self.collection_repo.create.return_value = Collection(id=1, name="Breaking Bad")
        result = self.use_case.execute("Breaking Bad")
        assert result.id == 1
        assert result.name == "Breaking Bad"
        assert result.source_count == 0
        self.collection_repo.create.assert_called_once()

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute("")

    def test_whitespace_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute("   ")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="200"):
            self.use_case.execute("a" * 201)

    def test_duplicate_name_raises(self) -> None:
        self.collection_repo.list_all.return_value = [
            Collection(id=1, name="Breaking Bad"),
        ]
        with pytest.raises(CollectionNameExistsError):
            self.use_case.execute("Breaking Bad")

    def test_strips_whitespace(self) -> None:
        self.collection_repo.list_all.return_value = []
        self.collection_repo.create.return_value = Collection(id=1, name="Breaking Bad")
        self.use_case.execute("  Breaking Bad  ")
        created = self.collection_repo.create.call_args[0][0]
        assert created.name == "Breaking Bad"
