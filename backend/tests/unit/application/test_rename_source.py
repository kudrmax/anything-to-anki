from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.rename_source import RenameSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestRenameSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.use_case = RenameSourceUseCase(source_repo=self.source_repo)

    def test_rename_success(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.NEW, title="Old",
        )
        self.use_case.execute(1, "New Title")
        self.source_repo.update_title.assert_called_once_with(1, "New Title")

    def test_rename_strips_whitespace(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Text", status=SourceStatus.NEW, title="Old",
        )
        self.use_case.execute(1, "  Trimmed  ")
        self.source_repo.update_title.assert_called_once_with(1, "Trimmed")

    def test_rename_empty_title_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute(1, "")

    def test_rename_whitespace_title_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            self.use_case.execute(1, "   ")

    def test_rename_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999, "Title")
