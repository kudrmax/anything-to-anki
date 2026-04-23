from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestListCollectionsUseCase:
    def setup_method(self) -> None:
        self.collection_repo = MagicMock()
        self.source_repo = MagicMock()
        self.use_case = ListCollectionsUseCase(
            collection_repo=self.collection_repo,
            source_repo=self.source_repo,
        )

    def test_empty_list(self) -> None:
        self.collection_repo.list_all.return_value = []
        self.source_repo.list_all.return_value = []
        result = self.use_case.execute()
        assert result == []

    def test_returns_collections_with_counts(self) -> None:
        self.collection_repo.list_all.return_value = [
            Collection(id=1, name="BB"),
            Collection(id=2, name="HP"),
        ]
        self.source_repo.list_all.return_value = [
            Source(id=10, raw_text="t", status=SourceStatus.NEW,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
                   collection_id=1),
            Source(id=11, raw_text="t", status=SourceStatus.NEW,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
                   collection_id=1),
            Source(id=12, raw_text="t", status=SourceStatus.NEW,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
                   collection_id=2),
            Source(id=13, raw_text="t", status=SourceStatus.NEW,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT),
        ]
        result = self.use_case.execute()
        assert len(result) == 2
        bb = next(r for r in result if r.name == "BB")
        hp = next(r for r in result if r.name == "HP")
        assert bb.source_count == 2
        assert hp.source_count == 1

    def test_sorted_by_name(self) -> None:
        self.collection_repo.list_all.return_value = [
            Collection(id=2, name="Zebra"),
            Collection(id=1, name="Alpha"),
        ]
        self.source_repo.list_all.return_value = []
        result = self.use_case.execute()
        assert result[0].name == "Alpha"
        assert result[1].name == "Zebra"
