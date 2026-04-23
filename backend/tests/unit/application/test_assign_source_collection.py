from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.assign_source_collection import AssignSourceToCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import CollectionNotFoundError, SourceNotFoundError
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestAssignSourceToCollectionUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.collection_repo = MagicMock()
        self.use_case = AssignSourceToCollectionUseCase(
            source_repo=self.source_repo,
            collection_repo=self.collection_repo,
        )

    def _make_source(self, source_id: int = 1) -> Source:
        return Source(
            id=source_id, raw_text="test", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )

    def test_assigns_source_to_collection(self) -> None:
        self.source_repo.get_by_id.return_value = self._make_source()
        self.collection_repo.get_by_id.return_value = Collection(id=5, name="BB")
        self.use_case.execute(1, 5)
        self.source_repo.update_collection.assert_called_once_with(1, 5)

    def test_removes_collection_from_source(self) -> None:
        self.source_repo.get_by_id.return_value = self._make_source()
        self.use_case.execute(1, None)
        self.source_repo.update_collection.assert_called_once_with(1, None)
        self.collection_repo.get_by_id.assert_not_called()

    def test_source_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999, 5)

    def test_collection_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = self._make_source()
        self.collection_repo.get_by_id.return_value = None
        with pytest.raises(CollectionNotFoundError):
            self.use_case.execute(1, 999)
