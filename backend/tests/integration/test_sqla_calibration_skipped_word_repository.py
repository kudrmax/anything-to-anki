from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.persistence.sqla_calibration_skipped_word_repository import (
    SqlaCalibrationSkippedWordRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.mark.integration
class TestSqlaCalibrationSkippedWordRepository:
    def test_add_and_list(self, db_session: Session) -> None:
        repo = SqlaCalibrationSkippedWordRepository(db_session)
        repo.add(["bush", "lord"])
        assert repo.lemmas() == {"bush", "lord"}
        assert repo.count() == 2

    def test_a_word_skipped_twice_is_kept_once(self, db_session: Session) -> None:
        repo = SqlaCalibrationSkippedWordRepository(db_session)
        repo.add(["bush"])
        repo.add(["bush", "lord"])
        assert repo.count() == 2

    def test_adding_nothing(self, db_session: Session) -> None:
        repo = SqlaCalibrationSkippedWordRepository(db_session)
        repo.add([])
        assert repo.count() == 0

    def test_clear(self, db_session: Session) -> None:
        repo = SqlaCalibrationSkippedWordRepository(db_session)
        repo.add(["bush"])
        repo.clear()
        assert repo.lemmas() == set()
        assert repo.count() == 0
