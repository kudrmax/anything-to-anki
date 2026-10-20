from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, delete, func, insert, literal_column, select

from backend.domain.entities.known_word import KnownWord
from backend.domain.entities.unknown_word import UnknownWord
from backend.domain.ports.word_mark_repository import WordMarkRepository
from backend.domain.value_objects.card_change import MarkChanged
from backend.domain.value_objects.word_mark import WordMark
from backend.infrastructure.persistence.models import KnownPosModel, WordMarkModel

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import InstrumentedAttribute, Session

    from backend.domain.ports.change_recorder import ChangeRecorder

ROW_ID = "rowid"


class SqlaWordMarkRepository(WordMarkRepository):
    """SQLAlchemy implementation of WordMarkRepository over word_marks and known_pos.

    An entry's id is its row's SQLite rowid: the tables have no id column of their own."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def mark_known(self, lemma: str, pos: str | None) -> KnownWord:
        key = lemma.lower()
        changed = self._set_mark(key, WordMark.KNOWN)
        held = self._pos_of(key)
        if None not in held and pos not in held:
            if pos is None:
                self._delete_pos(key)
            self._session.execute(insert(KnownPosModel).values(lemma=key, pos=pos))
            changed = True
        if changed:
            self._recorder.record(MarkChanged(key))
        covering = None if None in self._pos_of(key) else pos
        return next(e for e in self._known(key) if e.pos == covering)

    def mark_unknown(self, lemma: str) -> UnknownWord:
        key = lemma.lower()
        if self._set_mark(key, WordMark.UNKNOWN):
            self._recorder.record(MarkChanged(key))
        return self._unknown(key)[0]

    def remove_known_entry(self, lemma: str, pos: str | None) -> None:
        key = lemma.lower()
        mark = self._session.get(WordMarkModel, key)
        if mark is None or mark.mark != WordMark.KNOWN:
            return
        held = self._pos_of(key)
        if pos not in held:
            return
        self._session.execute(
            delete(KnownPosModel).where(KnownPosModel.lemma == key, _pos_is(pos)),
        )
        if held == {pos}:
            self._session.delete(mark)
            self._session.flush()
        self._recorder.record(MarkChanged(key))

    def remove_known(self, lemma: str) -> None:
        self._remove(lemma.lower(), WordMark.KNOWN)

    def remove_unknown(self, lemma: str) -> None:
        self._remove(lemma.lower(), WordMark.UNKNOWN)

    def known_entries(self) -> list[KnownWord]:
        return self._known(None)

    def unknown_entries(self) -> list[UnknownWord]:
        return self._unknown(None)

    def known_lemmas(self) -> set[str]:
        return set(self._lemmas(WordMark.KNOWN))

    def unknown_lemmas(self) -> set[str]:
        return set(self._lemmas(WordMark.UNKNOWN))

    def known_count(self) -> int:
        return self._count(WordMark.KNOWN)

    def unknown_count(self) -> int:
        return self._count(WordMark.UNKNOWN)

    def _set_mark(self, key: str, kind: WordMark) -> bool:
        """The lemma carries `kind`, set now if it carried no mark or the other one; a Known
        mark it replaces takes its parts of speech along. Whether anything changed."""
        mark = self._session.get(WordMarkModel, key)
        if mark is not None and mark.mark == kind:
            return False
        if mark is None:
            self._session.add(WordMarkModel(lemma=key, mark=kind, created_at=_now()))
        else:
            self._delete_pos(key)
            mark.mark = kind
            mark.created_at = _now()
        self._session.flush()
        return True

    def _remove(self, key: str, kind: WordMark) -> None:
        mark = self._session.get(WordMarkModel, key)
        if mark is None or mark.mark != kind:
            return
        self._delete_pos(key)
        self._session.delete(mark)
        self._session.flush()
        self._recorder.record(MarkChanged(key))

    def _delete_pos(self, key: str) -> None:
        self._session.execute(delete(KnownPosModel).where(KnownPosModel.lemma == key))

    def _pos_of(self, key: str) -> set[str | None]:
        rows = self._session.execute(
            select(KnownPosModel.pos).where(KnownPosModel.lemma == key),
        )
        return {pos for (pos,) in rows}

    def _known(self, key: str | None) -> list[KnownWord]:
        query = (
            select(
                literal_column(f"known_pos.{ROW_ID}", Integer), KnownPosModel.lemma,
                KnownPosModel.pos, WordMarkModel.created_at,
            )
            .join(WordMarkModel, WordMarkModel.lemma == KnownPosModel.lemma)
            .where(WordMarkModel.mark == WordMark.KNOWN)
            .where(*_one_lemma(KnownPosModel.lemma, key))
            .order_by(WordMarkModel.created_at.desc(), KnownPosModel.lemma, KnownPosModel.pos)
        )
        return [
            KnownWord(id=row_id, lemma=lemma, pos=pos, created_at=created_at)
            for row_id, lemma, pos, created_at in self._session.execute(query)
        ]

    def _unknown(self, key: str | None) -> list[UnknownWord]:
        query = (
            select(
                literal_column(f"word_marks.{ROW_ID}", Integer), WordMarkModel.lemma,
                WordMarkModel.created_at,
            )
            .where(WordMarkModel.mark == WordMark.UNKNOWN)
            .where(*_one_lemma(WordMarkModel.lemma, key))
            .order_by(WordMarkModel.created_at.desc(), WordMarkModel.lemma)
        )
        return [
            UnknownWord(id=row_id, lemma=lemma, created_at=created_at)
            for row_id, lemma, created_at in self._session.execute(query)
        ]

    def _lemmas(self, kind: WordMark) -> list[str]:
        return list(self._session.scalars(
            select(WordMarkModel.lemma).where(WordMarkModel.mark == kind),
        ))

    def _count(self, kind: WordMark) -> int:
        result = self._session.scalar(
            select(func.count()).select_from(WordMarkModel).where(WordMarkModel.mark == kind),
        )
        return result or 0


def _one_lemma(
    column: InstrumentedAttribute[str], key: str | None,
) -> tuple[ColumnElement[bool], ...]:
    return () if key is None else (column == key,)


def _pos_is(pos: str | None) -> ColumnElement[bool]:
    if pos is None:
        return KnownPosModel.pos.is_(None)
    return KnownPosModel.pos == pos


def _now() -> datetime:
    return datetime.now(tz=UTC)
