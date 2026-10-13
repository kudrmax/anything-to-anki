from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.unknown_word_repository import UnknownWordRepository
from backend.infrastructure.persistence.models import UnknownWordModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.unknown_word import UnknownWord


class SqlaUnknownWordRepository(UnknownWordRepository):
    """SQLAlchemy implementation of UnknownWordRepository; lemmas are stored lowercase."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lemma: str) -> UnknownWord:
        key = lemma.lower()
        existing = (
            self._session.query(UnknownWordModel).filter(UnknownWordModel.lemma == key).first()
        )
        if existing is not None:
            return existing.to_entity()
        model = UnknownWordModel(lemma=key)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def remove(self, unknown_word_id: int) -> None:
        model = self._session.get(UnknownWordModel, unknown_word_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def remove_by_lemma(self, lemma: str) -> None:
        self._session.query(UnknownWordModel).filter(
            UnknownWordModel.lemma == lemma.lower(),
        ).delete(synchronize_session="fetch")
        self._session.flush()

    def list_all(self) -> list[UnknownWord]:
        models = (
            self._session.query(UnknownWordModel)
            .order_by(UnknownWordModel.created_at.desc())
            .all()
        )
        return [m.to_entity() for m in models]

    def lemmas(self) -> set[str]:
        return {row.lemma for row in self._session.query(UnknownWordModel.lemma).all()}

    def count(self) -> int:
        result = self._session.query(func.count(UnknownWordModel.id)).scalar()
        return result or 0
