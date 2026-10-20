from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_stats import GetStatsUseCase

from tests.vocabulary_support import user_vocabulary


@pytest.mark.unit
class TestGetStatsUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.known_word_repo = MagicMock()
        self.export_queue = MagicMock()
        self.export_queue.for_all.side_effect = AssertionError("stats only count the queue")
        self.export_queue.pending_count.return_value = 0
        self.job_repo = MagicMock()
        self.job_repo.get_queue_summary.return_value = {}
        self.use_case = GetStatsUseCase(
            candidate_repo=self.candidate_repo,
            vocabulary=user_vocabulary(self.known_word_repo),
            export_queue=self.export_queue,
            job_repo=self.job_repo,
        )

    def test_returns_correct_counts(self) -> None:
        """Learning: words in Anki. Known: each lemma once, by the list or by the timer."""
        self.candidate_repo.count_learning_in_anki.return_value = 12
        self.candidate_repo.count_all.return_value = 120
        self.known_word_repo.known_lemmas.return_value = {"glare", "linger"}
        result = self.use_case.execute()
        assert result.learning_count == 12
        assert result.candidate_count == 120
        assert result.known_word_count == 2

    def test_returns_zeros_when_empty(self) -> None:
        self.candidate_repo.count_learning_in_anki.return_value = 0
        self.candidate_repo.count_all.return_value = 0
        result = self.use_case.execute()
        assert result.learning_count == 0
        assert result.candidate_count == 0
        assert result.known_word_count == 0
        assert result.export_pending_count == 0
        assert result.queue_active_count == 0

    def test_export_pending_count_excludes_already_exported(self) -> None:
        self.candidate_repo.count_learning_in_anki.return_value = 31
        self.export_queue.pending_count.return_value = 3
        result = self.use_case.execute()
        assert result.learning_count == 31
        assert result.export_pending_count == 3

    def test_queue_active_count_sums_queued_and_running_but_not_failed(self) -> None:
        self.job_repo.get_queue_summary.return_value = {
            "meaning": {"queued": 4, "running": 1, "failed": 2},
            "tts": {"queued": 3, "running": 0, "failed": 5},
        }
        result = self.use_case.execute()
        assert result.queue_active_count == 8
        self.job_repo.get_queue_summary.assert_called_once_with()
