from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestCreateSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.use_case = CreateSourceUseCase(source_repo=self.source_repo)

    def test_creates_source_with_new_status(self) -> None:
        self.source_repo.create.return_value = Source(
            id=1, raw_text="Hello world", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
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

    def test_creates_source_with_explicit_title(self) -> None:
        self.source_repo.create.return_value = Source(
            id=2, raw_text="Some text", status=SourceStatus.NEW, title="My Title",
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        self.use_case.execute("Some text", title="My Title")
        created_source = self.source_repo.create.call_args[0][0]
        assert created_source.title == "My Title"

    def test_auto_generates_title_when_none(self) -> None:
        self.source_repo.create.return_value = Source(
            id=3, raw_text="Hello world", status=SourceStatus.NEW, title="Hello world",
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        self.use_case.execute("Hello world")
        created_source = self.source_repo.create.call_args[0][0]
        assert created_source.title == "Hello world"

    def test_auto_generates_title_when_whitespace(self) -> None:
        self.source_repo.create.return_value = Source(
            id=4, raw_text="Hello world", status=SourceStatus.NEW, title="Hello world",
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        self.use_case.execute("Hello world", title="   ")
        created_source = self.source_repo.create.call_args[0][0]
        assert created_source.title == "Hello world"

    def test_auto_title_truncated_to_100_chars(self) -> None:
        long_text = "a" * 200
        self.source_repo.create.return_value = Source(
            id=5, raw_text=long_text, status=SourceStatus.NEW, title="a" * 100,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        self.use_case.execute(long_text)
        created_source = self.source_repo.create.call_args[0][0]
        assert len(created_source.title) == 100
