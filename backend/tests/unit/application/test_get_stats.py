from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_stats import GetStatsUseCase
from backend.application.utils.export_queue import ExportBatch
from backend.domain.value_objects.candidate_status import CandidateStatus


@pytest.mark.unit
class TestGetStatsUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.known_word_repo = MagicMock()
        self.export_queue = MagicMock()
        self.export_queue.for_all.return_value = ExportBatch(pending=[], exported_count=0)
        self.use_case = GetStatsUseCase(
            candidate_repo=self.candidate_repo,
            known_word_repo=self.known_word_repo,
            export_queue=self.export_queue,
        )

    def test_returns_correct_counts(self) -> None:
        self.candidate_repo.count_by_status.return_value = 7
        self.candidate_repo.count_all.return_value = 120
        self.known_word_repo.count.return_value = 43
        result = self.use_case.execute()
        assert result.learn_count == 7
        assert result.candidate_count == 120
        assert result.known_word_count == 43
        self.candidate_repo.count_by_status.assert_called_once_with(CandidateStatus.LEARN)
        self.known_word_repo.count.assert_called_once()

    def test_returns_zeros_when_empty(self) -> None:
        self.candidate_repo.count_by_status.return_value = 0
        self.candidate_repo.count_all.return_value = 0
        self.known_word_repo.count.return_value = 0
        result = self.use_case.execute()
        assert result.learn_count == 0
        assert result.candidate_count == 0
        assert result.known_word_count == 0
        assert result.export_pending_count == 0

    def test_export_pending_count_excludes_already_exported(self) -> None:
        self.candidate_repo.count_by_status.return_value = 31
        self.export_queue.for_all.return_value = ExportBatch(
            pending=[MagicMock(), MagicMock(), MagicMock()],
            exported_count=28,
        )
        result = self.use_case.execute()
        assert result.learn_count == 31
        assert result.export_pending_count == 3
