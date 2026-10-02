from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.word_decision import WordDecision
from backend.infrastructure.persistence.sqla_word_decision_repository import (
    SqlaWordDecisionRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.mark.integration
class TestSqlaWordDecisionRepository:
    def test_record_and_list(self, db_session: Session) -> None:
        repo = SqlaWordDecisionRepository(db_session)
        repo.record(WordDecision("lizard", 3.63, is_known=False))
        assert repo.list_all() == [WordDecision("lizard", 3.63, is_known=False)]

    def test_new_decision_replaces_the_old_one(self, db_session: Session) -> None:
        repo = SqlaWordDecisionRepository(db_session)
        repo.record(WordDecision("lizard", 3.63, is_known=False))
        repo.record(WordDecision("lizard", 3.63, is_known=True))
        assert repo.list_all() == [WordDecision("lizard", 3.63, is_known=True)]

    def test_forget(self, db_session: Session) -> None:
        repo = SqlaWordDecisionRepository(db_session)
        repo.record(WordDecision("lizard", 3.63, is_known=False))
        repo.forget("lizard")
        assert repo.list_all() == []
