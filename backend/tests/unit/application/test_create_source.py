from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestCreateSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.use_case = CreateSourceUseCase(source_repo=self.source_repo)

    def test_creates_source_with_new_status(self) -> None:
        self.source_repo.create.return_value = Source(
            id=1, raw_text="Hello world", status=SourceStatus.NEW,
        )
        result = self.use_case.execute("Hello world")
        assert result.id == 1
        assert result.status == SourceStatus.NEW
        self.source_repo.create.assert_called_once()
        created_source = self.source_repo.create.call_args[0][0]
        assert created_source.raw_text == "Hello world"
        assert created_source.status == SourceStatus.NEW

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute("   \n  ")
