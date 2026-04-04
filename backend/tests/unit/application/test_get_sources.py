from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestGetSourcesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.use_case = GetSourcesUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
        )

    def test_list_all(self) -> None:
        self.source_repo.list_all.return_value = [
            Source(id=1, raw_text="Text one", status=SourceStatus.NEW),
            Source(id=2, raw_text="Text two", status=SourceStatus.DONE),
        ]
        self.candidate_repo.get_by_source.return_value = []
        result = self.use_case.list_all()
        assert len(result) == 2
        assert result[0].id == 1

    def test_get_by_id_found(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.DONE,
        )
        self.candidate_repo.get_by_source.return_value = []
        result = self.use_case.get_by_id(1)
        assert result.id == 1

    def test_get_by_id_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.get_by_id(999)
