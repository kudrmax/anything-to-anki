from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select, update

from backend.domain.ports.card_state_store import CardStateStore
from backend.domain.value_objects.card_choice import DecisionStatus
from backend.domain.value_objects.card_state_rows import (
    CardStateRow,
    PhraseWordKind,
    PhraseWordRow,
    StoredCardState,
    StoredCardStates,
    WordStateRow,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase_newness import PhraseNewness
from backend.domain.value_objects.user_knowledge import Newness
from backend.infrastructure.persistence.card_state_codecs import (
    NewCountsByStepCodec,
    SectionsByStepCodec,
)
from backend.infrastructure.persistence.models import (
    PROJECTION_META_ID,
    CardStateModel,
    PhraseWordModel,
    ProjectionMetaModel,
    WordStateModel,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from sqlalchemy import ColumnElement, Row, Table
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.card_state_rows import CardStates

# Rows are written by plain INSERTs that bypass the ORM: the session never holds them.
_TABLES = CardStateModel.metadata.tables
_CARDS = _TABLES[CardStateModel.__tablename__]
_WORDS = _TABLES[WordStateModel.__tablename__]
_PHRASE_WORDS = _TABLES[PhraseWordModel.__tablename__]
_META = _TABLES[ProjectionMetaModel.__tablename__]


class SqlaCardStateStore(CardStateStore):
    """The projection tables card_states, word_states, phrase_words and projection_meta."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def next_revision(self) -> int:
        revision: int = self._session.execute(
            update(_META)
            .where(_META.c.id == PROJECTION_META_ID)
            .values(revision=_META.c.revision + 1)
            .returning(_META.c.revision)
        ).scalar_one()
        return revision

    def replace_all(self, states: CardStates, revision: int) -> None:
        session = self._session
        session.execute(
            update(_CARDS)
            .where(_CARDS.c.removed.is_(False))
            .values(removed=True, revision=revision)
        )
        self.write_cards(states.cards, revision)
        session.execute(delete(_WORDS))
        self._insert_many(_WORDS, _WORD_COLUMNS, [_word_values(row) for row in states.words])
        self._replace_all_phrase_words(states.phrase_words)

    def _replace_all_phrase_words(self, rows: Collection[PhraseWordRow]) -> None:
        """Only the rows that differ are written: after a restart nearly all are as stored,
        and rewriting a book's million rows and their index took a quarter of the rebuild.
        The table is read in its key order, so the rows of a rebuild, in that order too,
        match it as a list unless something changed."""
        wanted = sorted(
            (_phrase_word_values(row) for row in rows), key=lambda values: values[2:4],
        )
        cursor = self._session.connection().connection.cursor()
        try:
            cursor.execute(
                f"SELECT {', '.join(_PHRASE_WORD_COLUMNS)} FROM {_PHRASE_WORDS.name}"  # noqa: S608 — model names
                " ORDER BY phrase_id, position",
            )
            stored = list(cursor.fetchall())
        finally:
            cursor.close()
        if stored == wanted:
            return
        by_key = {values[2:4]: values for values in wanted}
        kept = {values[2:4]: values for values in stored}
        gone = [key for key in kept if key not in by_key]
        changed = [values for key, values in by_key.items() if kept.get(key) != values]
        if gone:
            self._session.connection().exec_driver_sql(
                f"DELETE FROM {_PHRASE_WORDS.name} WHERE phrase_id = ? AND position = ?",  # noqa: S608 — model names
                gone,
            )
        self._insert_many(_PHRASE_WORDS, _PHRASE_WORD_COLUMNS, changed, replace=True)

    def _insert_many(
        self, table: Table, columns: tuple[str, ...], rows: list[tuple[object, ...]],
        *, replace: bool = False,
    ) -> None:
        """Plain values straight to the driver: a whole book's other words go in at once,
        and SQLAlchemy's binding row by row would take most of the time."""
        if not rows:
            return
        names = ", ".join(table.c[column].name for column in columns)
        marks = ", ".join("?" for _ in columns)
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        self._session.connection().exec_driver_sql(
            f"{verb} INTO {table.name} ({names}) VALUES ({marks})",  # noqa: S608 — model names
            rows,
        )

    def ticked_at(self) -> datetime | None:
        moment: datetime | None = self._session.execute(
            select(_META.c.ticked_at).where(_META.c.id == PROJECTION_META_ID)
        ).scalar_one()
        return moment

    def set_ticked_at(self, moment: datetime) -> None:
        self._session.execute(
            update(_META).where(_META.c.id == PROJECTION_META_ID).values(ticked_at=moment)
        )

    def lemmas_changing_by(self, moment: datetime) -> set[str]:
        """By the partial index of `changes_at`."""
        return set(self._session.scalars(
            select(_CARDS.c.lemma)
            .where(
                _CARDS.c.changes_at.is_not(None),
                _CARDS.c.changes_at <= moment,
                _CARDS.c.removed.is_(False),
            )
            .distinct()
        ))

    def read_all(self) -> StoredCardStates:
        session = self._session
        return StoredCardStates(
            cards=tuple(_stored_card(row) for row in session.execute(select(_CARDS))),
            words=tuple(_word_row(row) for row in session.execute(select(_WORDS))),
            phrase_words=tuple(
                _phrase_word_row(row) for row in session.execute(select(_PHRASE_WORDS))
            ),
            revision=session.execute(
                select(_META.c.revision).where(_META.c.id == PROJECTION_META_ID)
            ).scalar_one(),
        )

    def cards(self, phrase_ids: Collection[int]) -> dict[int, StoredCardState]:
        """Read on the driver's own cursor, as `phrase_words`."""
        cursor = self._session.connection().connection.cursor()
        found: dict[int, StoredCardState] = {}
        try:
            for chunk in chunks(sorted(phrase_ids)):
                marks = ", ".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT {_CARD_NAMES} FROM {_CARDS.name}"  # noqa: S608 — model names
                    f" WHERE phrase_id IN ({marks})",
                    chunk,
                )
                for values in cursor.fetchall():
                    card = _plain_stored_card(values)
                    found[card.row.phrase_id] = card
        finally:
            cursor.close()
        return found

    def live_cards_of_words(self, word_ids: Collection[int]) -> list[StoredCardState]:
        return [
            card
            for chunk in chunks(sorted(word_ids))
            for card in self._cards(_CARDS.c.word_id.in_(chunk), _CARDS.c.removed.is_(False))
        ]

    def live_cards_of_source(self, source_id: int) -> list[StoredCardState]:
        return self._cards(_CARDS.c.source_id == source_id, _CARDS.c.removed.is_(False))

    def _cards(self, *where: ColumnElement[bool]) -> list[StoredCardState]:
        return [_stored_card(row) for row in self._session.execute(select(_CARDS).where(*where))]

    def words(self, word_ids: Collection[int]) -> dict[int, WordStateRow]:
        return {
            word.word_id: word
            for chunk in chunks(sorted(word_ids))
            for word in self._words(_WORDS.c.word_id.in_(chunk))
        }

    def words_of_source(
        self, source_id: int, lemmas: Collection[str] | None = None,
    ) -> list[WordStateRow]:
        if lemmas is None:
            return self._words(_WORDS.c.source_id == source_id)
        return [
            word
            for chunk in chunks(sorted(lemmas))
            for word in self._words(_WORDS.c.source_id == source_id, _WORDS.c.lemma.in_(chunk))
        ]

    def _words(self, *where: ColumnElement[bool]) -> list[WordStateRow]:
        return [_word_row(row) for row in self._session.execute(select(_WORDS).where(*where))]

    def phrase_newness(self, phrase_ids: Collection[int]) -> dict[int, PhraseNewness]:
        """Read on the driver's own cursor: a frequent lemma's phrases hold tens of thousands
        of words, and SQLAlchemy's rows would take most of the time."""
        cursor = self._session.connection().connection.cursor()
        words: dict[int, list[tuple[str, float, Newness]]] = {}
        try:
            for chunk in chunks(sorted(phrase_ids)):
                marks = ", ".join("?" for _ in chunk)
                cursor.execute(
                    "SELECT phrase_id, phrase_lemma, zipf, newness"
                    f" FROM {_PHRASE_WORDS.name} WHERE phrase_id IN ({marks})"  # noqa: S608 — model names
                    " ORDER BY phrase_id, position",
                    chunk,
                )
                for phrase_id, phrase_lemma, zipf, newness in cursor.fetchall():
                    words.setdefault(phrase_id, []).append(
                        (phrase_lemma, zipf, _NEWNESS[newness]),
                    )
        finally:
            cursor.close()
        return {phrase_id: PhraseNewness.of(found) for phrase_id, found in words.items()}

    def phrase_word_kinds(self, lemmas: Collection[str]) -> set[PhraseWordKind]:
        columns = _PHRASE_WORDS.c
        return {
            PhraseWordKind(lemma=lemma, content=bool(content), level=CEFRLevel[level])
            for chunk in chunks(sorted(lemmas))
            for lemma, content, level in self._session.execute(
                select(columns.lemma, columns.content, columns.level)
                .where(columns.lemma.in_(chunk))
                .distinct()
            )
        }

    def set_newness(self, kind: PhraseWordKind, newness: Newness) -> set[int]:
        columns = _PHRASE_WORDS.c
        return set(self._session.scalars(
            update(_PHRASE_WORDS)
            .where(
                columns.lemma == kind.lemma,
                columns.content.is_(kind.content),
                columns.level == kind.level.name,
                columns.newness != newness.value,
            )
            .values(newness=newness.value)
            .returning(columns.phrase_id)
        ))

    def write_cards(self, rows: Collection[CardStateRow], revision: int) -> None:
        """An upsert on the driver, not a REPLACE: a stored card is updated in place, so only
        the indexes of the columns that changed are touched; `changes_at` goes through its
        column type, as SQLAlchemy writes it."""
        if rows:
            dialect = self._session.get_bind().dialect
            moment = _CARDS.c.changes_at.type.dialect_impl(dialect).bind_processor(dialect)
            assert moment is not None
            self._session.connection().exec_driver_sql(
                _UPSERT_CARD,
                [
                    (
                        row.phrase_id, row.source_id, row.word_id, row.lemma, row.is_done,
                        row.wants_generation, SectionsByStepCodec.encode(row.sections),
                        NewCountsByStepCodec.encode(row.new_counts), moment(row.changes_at),
                        revision, False,
                    )
                    for row in rows
                ],
            )

    def write_sections(self, rows: Collection[CardStateRow], revision: int) -> None:
        """Only the columns that changed: the other ones are indexed."""
        if rows:
            self._session.connection().exec_driver_sql(
                f"UPDATE {_CARDS.name} SET sections = ?, new_counts = ?, revision = ?"  # noqa: S608 — model names
                " WHERE phrase_id = ?",
                [
                    (
                        SectionsByStepCodec.encode(row.sections),
                        NewCountsByStepCodec.encode(row.new_counts), revision, row.phrase_id,
                    )
                    for row in rows
                ],
            )

    def remove_cards(self, phrase_ids: Collection[int], revision: int) -> None:
        for chunk in chunks(sorted(phrase_ids)):
            self._session.execute(
                update(_CARDS)
                .where(_CARDS.c.phrase_id.in_(chunk))
                .values(removed=True, revision=revision)
            )
            self._session.execute(delete(_PHRASE_WORDS).where(_PHRASE_WORDS.c.phrase_id.in_(chunk)))

    def replace_phrase_words(
        self, phrase_ids: Collection[int], rows: Collection[PhraseWordRow],
    ) -> None:
        for chunk in chunks(sorted(phrase_ids)):
            self._session.execute(delete(_PHRASE_WORDS).where(_PHRASE_WORDS.c.phrase_id.in_(chunk)))
        self._insert_many(
            _PHRASE_WORDS, _PHRASE_WORD_COLUMNS, [_phrase_word_values(row) for row in rows],
        )

    def write_words(self, rows: Collection[WordStateRow]) -> None:
        self._insert_many(
            _WORDS, _WORD_COLUMNS, [_word_values(row) for row in rows], replace=True,
        )

    def delete_words(self, word_ids: Collection[int]) -> None:
        for chunk in chunks(sorted(word_ids)):
            self._session.execute(delete(_WORDS).where(_WORDS.c.word_id.in_(chunk)))

    def touch_cards(
        self, phrase_ids: Collection[int], word_ids: Collection[int], revision: int,
    ) -> None:
        for column, ids in ((_CARDS.c.phrase_id, phrase_ids), (_CARDS.c.word_id, word_ids)):
            for chunk in chunks(sorted(ids)):
                self._session.execute(
                    update(_CARDS)
                    .where(column.in_(chunk), _CARDS.c.removed.is_(False))
                    .values(revision=revision)
                )


_WORD_COLUMNS = ("word_id", "source_id", "lemma", "status")


def _word_values(row: WordStateRow) -> tuple[object, ...]:
    """In the order of _WORD_COLUMNS."""
    return (row.word_id, row.source_id, row.lemma, row.status.value)


_PHRASE_WORD_COLUMNS = (
    "lemma", "phrase_lemma", "phrase_id", "position", "zipf", "content", "level", "newness",
)
_NEWNESS: Mapping[str, Newness] = MappingProxyType({kind.value: kind for kind in Newness})


def _phrase_word_values(row: PhraseWordRow) -> tuple[object, ...]:
    """In the order of _PHRASE_WORD_COLUMNS."""
    return (
        row.lemma, row.phrase_lemma, row.phrase_id, row.position, row.zipf, row.content,
        row.level.name, row.newness.value,
    )


_CARD_COLUMNS = (
    "phrase_id", "source_id", "word_id", "lemma", "is_done", "wants_generation", "sections",
    "new_counts", "changes_at", "revision", "removed",
)
_CARD_NAMES = ", ".join(_CARD_COLUMNS)
_UPSERT_CARD = (
    f"INSERT INTO {_CARDS.name} ({_CARD_NAMES})"  # noqa: S608 — model names
    f" VALUES ({', '.join('?' for _ in _CARD_COLUMNS)})"
    f" ON CONFLICT ({_CARD_COLUMNS[0]}) DO UPDATE SET "
    + ", ".join(f"{column} = excluded.{column}" for column in _CARD_COLUMNS[1:])
)


# Any: the driver's rows are untyped; each value is read into its typed field here.
def _plain_stored_card(values: tuple[Any, ...]) -> StoredCardState:
    """A row of _CARD_COLUMNS as the driver gives it: `changes_at` as the UTC text the
    column type stores."""
    (
        phrase_id, source_id, word_id, lemma, is_done, wants_generation, sections, new_counts,
        changes_at, revision, removed,
    ) = values
    return StoredCardState(
        row=CardStateRow(
            phrase_id=phrase_id,
            source_id=source_id,
            word_id=word_id,
            lemma=lemma,
            is_done=bool(is_done),
            wants_generation=bool(wants_generation),
            sections=SectionsByStepCodec.decode(sections),
            new_counts=NewCountsByStepCodec.decode(new_counts),
            changes_at=(
                datetime.fromisoformat(changes_at).replace(tzinfo=UTC)
                if changes_at is not None else None
            ),
        ),
        revision=revision,
        removed=bool(removed),
    )


def _stored_card(row: Row[tuple[object, ...]]) -> StoredCardState:
    m = row._mapping
    return StoredCardState(
        row=CardStateRow(
            phrase_id=m[_CARDS.c.phrase_id],
            source_id=m[_CARDS.c.source_id],
            word_id=m[_CARDS.c.word_id],
            lemma=m[_CARDS.c.lemma],
            is_done=m[_CARDS.c.is_done],
            wants_generation=m[_CARDS.c.wants_generation],
            sections=SectionsByStepCodec.decode(m[_CARDS.c.sections]),
            new_counts=NewCountsByStepCodec.decode(m[_CARDS.c.new_counts]),
            changes_at=m[_CARDS.c.changes_at],
        ),
        revision=m[_CARDS.c.revision],
        removed=m[_CARDS.c.removed],
    )


def _word_row(row: Row[tuple[object, ...]]) -> WordStateRow:
    m = row._mapping
    return WordStateRow(
        word_id=m[_WORDS.c.word_id],
        source_id=m[_WORDS.c.source_id],
        lemma=m[_WORDS.c.lemma],
        status=DecisionStatus(m[_WORDS.c.status]),
    )


def _phrase_word_row(row: Row[tuple[object, ...]]) -> PhraseWordRow:
    m = row._mapping
    return PhraseWordRow(
        lemma=m[_PHRASE_WORDS.c.lemma],
        phrase_lemma=m[_PHRASE_WORDS.c.phrase_lemma],
        phrase_id=m[_PHRASE_WORDS.c.phrase_id],
        position=m[_PHRASE_WORDS.c.position],
        zipf=m[_PHRASE_WORDS.c.zipf],
        content=m[_PHRASE_WORDS.c.content],
        level=CEFRLevel[m[_PHRASE_WORDS.c.level]],
        newness=Newness(m[_PHRASE_WORDS.c.newness]),
    )
