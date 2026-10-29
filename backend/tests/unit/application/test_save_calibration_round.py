from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.save_calibration_round import SaveCalibrationRoundUseCase

from tests.vocabulary_support import user_vocabulary


@pytest.mark.unit
class TestSaveCalibrationRoundUseCase:
    def setup_method(self) -> None:
        self.known_word_repo = MagicMock()
        self.skipped_words = MagicMock()
        self.use_case = SaveCalibrationRoundUseCase(
            vocabulary=user_vocabulary(self.known_word_repo),
            skipped_words=self.skipped_words,
            unit_of_work=MagicMock(),
        )

    def test_tapped_words_become_known(self) -> None:
        self.use_case.execute(shown=["elaborate", "nuance"], known=["nuance"])

        self.known_word_repo.mark_known.assert_called_once_with("nuance", None)

    def test_words_not_tapped_are_skipped(self) -> None:
        self.use_case.execute(shown=["elaborate", "nuance", "drift"], known=["nuance"])

        self.skipped_words.add.assert_called_once_with({"elaborate", "drift"})

    def test_a_round_with_every_word_tapped_skips_nothing(self) -> None:
        self.use_case.execute(shown=["nuance"], known=["nuance"])

        self.skipped_words.add.assert_called_once_with(set())
