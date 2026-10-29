from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.calibration_skipped_word_repository import (
        CalibrationSkippedWordRepository,
    )
    from backend.domain.ports.unit_of_work import UnitOfWork


class SaveCalibrationRoundUseCase:
    """Ends a calibration round: the tapped words become known, the others are skipped,
    so calibration does not ask any of them again."""

    def __init__(
        self,
        vocabulary: UserVocabulary,
        skipped_words: CalibrationSkippedWordRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._vocabulary = vocabulary
        self._skipped_words = skipped_words
        self._unit_of_work = unit_of_work

    def execute(self, shown: list[str], known: list[str]) -> None:
        with self._unit_of_work.write():
            for lemma in known:
                self._vocabulary.mark_known(lemma, None)
            self._skipped_words.add(set(shown) - set(known))
