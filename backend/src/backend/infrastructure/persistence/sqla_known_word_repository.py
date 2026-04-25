from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.known_word_repository import KnownWordRepository
from backend.infrastructure.persistence.models import KnownWordModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.known_word import KnownWord


class SqlaKnownWordRepository(KnownWordRepository):
    """SQLAlchemy implementation of KnownWordRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lemma: str, pos: str | None) -> KnownWord:
        query = self._session.query(KnownWordModel).filter(
            KnownWordModel.lemma == lemma,
        )
        if pos is None:
            query = query.filter(KnownWordModel.pos.is_(None))
        else:
            query = query.filter(KnownWordModel.pos == pos)
        existing = query.first()
        if existing:
            return existing.to_entity()
        model = KnownWordModel(lemma=lemma, pos=pos)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def remove(self, known_word_id: int) -> None:
        model = self._session.get(KnownWordModel, known_word_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def list_all(self) -> list[KnownWord]:
        models = (
            self._session.query(KnownWordModel).order_by(KnownWordModel.created_at.desc()).all()
        )
        return [m.to_entity() for m in models]

    def exists(self, lemma: str, pos: str | None) -> bool:
        query = self._session.query(KnownWordModel).filter(
            KnownWordModel.lemma == lemma,
        )
        if pos is None:
            query = query.filter(KnownWordModel.pos.is_(None))
        else:
            query = query.filter(KnownWordModel.pos == pos)
        return query.first() is not None

    def get_all_pairs(self) -> set[tuple[str, str | None]]:
        rows = self._session.query(KnownWordModel.lemma, KnownWordModel.pos).all()
        return {(r.lemma, r.pos) for r in rows}

    def count(self) -> int:
        result = self._session.query(func.count(KnownWordModel.id)).scalar()
        return result or 0
