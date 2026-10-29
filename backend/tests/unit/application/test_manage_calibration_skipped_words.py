from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_calibration_skipped_words import (
    ManageCalibrationSkippedWordsUseCase,
)


@pytest.mark.unit
class TestManageCalibrationSkippedWordsUseCase:
    def setup_method(self) -> None:
        self.skipped_words = MagicMock()
        self.use_case = ManageCalibrationSkippedWordsUseCase(
            skipped_words=self.skipped_words, unit_of_work=MagicMock(),
        )

    def test_summary_counts_skipped_words(self) -> None:
        self.skipped_words.count.return_value = 312

        assert self.use_case.summary().count == 312

    def test_forget_clears_skipped_words(self) -> None:
        self.use_case.forget()

        self.skipped_words.clear.assert_called_once_with()
