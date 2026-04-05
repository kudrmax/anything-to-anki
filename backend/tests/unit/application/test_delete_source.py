from unittest.mock import MagicMock, call

import pytest

from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceIsProcessingError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestDeleteSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.use_case = DeleteSourceUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
        )

    def test_deletes_candidates_then_source(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.DONE
        )
        manager = MagicMock()
        manager.attach_mock(self.candidate_repo.delete_by_source, "delete_by_source")
        manager.attach_mock(self.source_repo.delete, "delete")

        self.use_case.execute(1)

        assert manager.mock_calls == [
            call.delete_by_source(1),
            call.delete(1),
        ]

    def test_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)
        self.candidate_repo.delete_by_source.assert_not_called()
        self.source_repo.delete.assert_not_called()

    def test_processing_raises(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING
        )
        with pytest.raises(SourceIsProcessingError):
            self.use_case.execute(1)
        self.candidate_repo.delete_by_source.assert_not_called()
        self.source_repo.delete.assert_not_called()
