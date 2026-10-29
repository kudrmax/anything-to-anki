from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.bootstrap_dtos import CalibrationSkippedWordsDTO

if TYPE_CHECKING:
    from backend.domain.ports.calibration_skipped_word_repository import (
        CalibrationSkippedWordRepository,
    )
    from backend.domain.ports.unit_of_work import UnitOfWork


class ManageCalibrationSkippedWordsUseCase:
    """How many words calibration will not ask again, and forgetting them so it asks again."""

    def __init__(
        self, skipped_words: CalibrationSkippedWordRepository, unit_of_work: UnitOfWork,
    ) -> None:
        self._skipped_words = skipped_words
        self._unit_of_work = unit_of_work

    def summary(self) -> CalibrationSkippedWordsDTO:
        return CalibrationSkippedWordsDTO(count=self._skipped_words.count())

    def forget(self) -> None:
        with self._unit_of_work.write():
            self._skipped_words.clear()
