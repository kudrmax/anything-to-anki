from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.known_word_repository import KnownWordRepository
from backend.domain.value_objects.card_change import MarkChanged
from backend.infrastructure.persistence.models import KnownWordModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Query, Session

    from backend.domain.entities.known_word import KnownWord
    from backend.domain.ports.change_recorder import ChangeRecorder


class SqlaKnownWordRepository(KnownWordRepository):
    """SQLAlchemy implementation of KnownWordRepository."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

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
        self._recorder.record(MarkChanged(lemma))
        return model.to_entity()

    def remove(self, known_word_id: int) -> None:
        model = self._session.get(KnownWordModel, known_word_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            self._recorder.record(MarkChanged(model.lemma))

    def list_all(self) -> list[KnownWord]:
        models = (
            self._session.query(KnownWordModel).order_by(KnownWordModel.created_at.desc()).all()
        )
        return [m.to_entity() for m in models]

    def remove_by_lemma(self, lemma: str, pos: str | None) -> None:
        removed = self._matching(lemma, pos).delete(synchronize_session="fetch")
        self._session.flush()
        if removed:
            self._recorder.record(MarkChanged(lemma))

    def remove_every_pos(self, lemma: str) -> None:
        removed = self._session.query(KnownWordModel).filter(
            func.lower(KnownWordModel.lemma) == lemma.lower(),
        ).delete(synchronize_session="fetch")
        self._session.flush()
        if removed:
            self._recorder.record(MarkChanged(lemma))

    def exists(self, lemma: str, pos: str | None) -> bool:
        return self._matching(lemma, pos).first() is not None

    def _matching(self, lemma: str, pos: str | None) -> Query[KnownWordModel]:
        query = self._session.query(KnownWordModel).filter(KnownWordModel.lemma == lemma)
        if pos is None:
            return query.filter(KnownWordModel.pos.is_(None))
        return query.filter(KnownWordModel.pos == pos)

    def get_all_pairs(self) -> set[tuple[str, str | None]]:
        rows = self._session.query(KnownWordModel.lemma, KnownWordModel.pos).all()
        return {(r.lemma, r.pos) for r in rows}

    def count(self) -> int:
        result = self._session.query(func.count(KnownWordModel.id)).scalar()
        return result or 0
