from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNotFoundError


@pytest.mark.unit
class TestDeleteCollectionUseCase:
    def setup_method(self) -> None:
        self.collection_repo = MagicMock()
        self.use_case = DeleteCollectionUseCase(collection_repo=self.collection_repo)

    def test_deletes_collection(self) -> None:
        self.collection_repo.get_by_id.return_value = Collection(id=1, name="Breaking Bad")
        self.use_case.execute(1)
        self.collection_repo.delete.assert_called_once_with(1)

    def test_not_found_raises(self) -> None:
        self.collection_repo.get_by_id.return_value = None
        with pytest.raises(CollectionNotFoundError):
            self.use_case.execute(999)
