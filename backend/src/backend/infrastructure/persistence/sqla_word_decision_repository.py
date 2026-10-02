from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.word_decision_repository import WordDecisionRepository
from backend.infrastructure.persistence.models import WordDecisionModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.word_decision import WordDecision


class SqlaWordDecisionRepository(WordDecisionRepository):
    """SQLAlchemy implementation of WordDecisionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, decision: WordDecision) -> None:
        self._session.merge(WordDecisionModel(
            lemma=decision.lemma,
            zipf_frequency=decision.zipf_frequency,
            is_known=decision.is_known,
        ))
        self._session.flush()

    def forget(self, lemma: str) -> None:
        self._session.query(WordDecisionModel).filter(
            WordDecisionModel.lemma == lemma,
        ).delete(synchronize_session="fetch")
        self._session.flush()

    def list_all(self) -> list[WordDecision]:
        return [m.to_entity() for m in self._session.query(WordDecisionModel).all()]
