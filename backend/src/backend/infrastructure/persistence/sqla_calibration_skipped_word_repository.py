from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.domain.ports.calibration_skipped_word_repository import (
    CalibrationSkippedWordRepository,
)
from backend.infrastructure.persistence.models import CalibrationSkippedWordModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session


class SqlaCalibrationSkippedWordRepository(CalibrationSkippedWordRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lemmas: Iterable[str]) -> None:
        rows = [{"lemma": lemma} for lemma in set(lemmas)]
        if rows:
            statement = sqlite_insert(CalibrationSkippedWordModel).on_conflict_do_nothing()
            self._session.execute(statement, rows)

    def lemmas(self) -> set[str]:
        return set(self._session.scalars(select(CalibrationSkippedWordModel.lemma)))

    def count(self) -> int:
        statement = select(func.count()).select_from(CalibrationSkippedWordModel)
        return self._session.scalar(statement) or 0

    def clear(self) -> None:
        self._session.execute(delete(CalibrationSkippedWordModel))
