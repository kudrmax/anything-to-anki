from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from backend.domain.ports.card_state_store import CardStateStore
from backend.domain.value_objects.card_choice import DecisionStatus
from backend.domain.value_objects.card_state_rows import (
    CardStateRow,
    PhraseWordRow,
    StoredCardState,
    StoredCardStates,
    WordStateRow,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
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

if TYPE_CHECKING:
    from sqlalchemy import Row, Table
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
        if states.cards:
            session.execute(
                _CARDS.insert().prefix_with("OR REPLACE"),
                [_card_values(row, revision) for row in states.cards],
            )
        session.execute(delete(_WORDS))
        self._insert_many(_WORDS, _WORD_COLUMNS, [_word_values(row) for row in states.words])
        session.execute(delete(_PHRASE_WORDS))
        self._insert_many(
            _PHRASE_WORDS, _PHRASE_WORD_COLUMNS,
            [_phrase_word_values(row) for row in states.phrase_words],
        )

    def _insert_many(
        self, table: Table, columns: tuple[str, ...], rows: list[tuple[object, ...]],
    ) -> None:
        """Plain values straight to the driver: a whole book's other words go in at once,
        and SQLAlchemy's binding row by row would take most of the time."""
        if not rows:
            return
        names = ", ".join(table.c[column].name for column in columns)
        marks = ", ".join("?" for _ in columns)
        self._session.connection().exec_driver_sql(
            f"INSERT INTO {table.name} ({names}) VALUES ({marks})",  # noqa: S608 — model names
            rows,
        )

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


def _card_values(row: CardStateRow, revision: int) -> dict[str, object]:
    return {
        "phrase_id": row.phrase_id,
        "source_id": row.source_id,
        "word_id": row.word_id,
        "lemma": row.lemma,
        "is_done": row.is_done,
        "wants_generation": row.wants_generation,
        "sections": SectionsByStepCodec.encode(row.sections),
        "new_counts": NewCountsByStepCodec.encode(row.new_counts),
        "changes_at": row.changes_at,
        "revision": revision,
        "removed": False,
    }


_WORD_COLUMNS = ("word_id", "source_id", "lemma", "status")


def _word_values(row: WordStateRow) -> tuple[object, ...]:
    """In the order of _WORD_COLUMNS."""
    return (row.word_id, row.source_id, row.lemma, row.status.value)


_PHRASE_WORD_COLUMNS = ("lemma", "phrase_id", "position", "zipf", "content", "level", "newness")


def _phrase_word_values(row: PhraseWordRow) -> tuple[object, ...]:
    """In the order of _PHRASE_WORD_COLUMNS."""
    return (
        row.lemma, row.phrase_id, row.position, row.zipf, row.content, row.level.name,
        row.newness.value,
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
        phrase_id=m[_PHRASE_WORDS.c.phrase_id],
        position=m[_PHRASE_WORDS.c.position],
        zipf=m[_PHRASE_WORDS.c.zipf],
        content=m[_PHRASE_WORDS.c.content],
        level=CEFRLevel[m[_PHRASE_WORDS.c.level]],
        newness=Newness(m[_PHRASE_WORDS.c.newness]),
    )
