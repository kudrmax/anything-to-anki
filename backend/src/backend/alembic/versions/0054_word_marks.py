"""Known and Unknown become one mark per lemma: word_marks, with the Known parts of speech
in known_pos. Both keep an INTEGER PRIMARY KEY id, stable across VACUUM: the API hands
the ids out as removal keys.

Revision ID: 0054
Revises: 0053

The two lists merge by lower(lemma); a merged mark is as old as its newest row. A lemma in
both lists keeps the mark set later (Unknown on a tie). An empty pos means any part of speech
and absorbs the others; a lemma has at most one such row. Every case-merge, resolved
conflict (with the Known pos rows an Unknown win drops) and absorbed pos goes to
migration-0054.log beside the database file, after a header line naming the run.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

KNOWN = "known"
UNKNOWN = "unknown"
LOG_NAME = "migration-0054.log"
ANY_POS = "any"
ANY_POS_INDEX = "uq_known_pos_any"


class _Lemma:
    """Every old row of one lower-case lemma."""

    def __init__(self) -> None:
        self.spellings: set[str] = set()
        self.known_at: str | None = None
        self.unknown_at: str | None = None
        self.pos: set[str | None] = set()

    def see_known(self, lemma: str, pos: str | None, created_at: str) -> None:
        self.spellings.add(lemma)
        self.pos.add(pos)
        self.known_at = max(self.known_at or created_at, created_at)

    def see_unknown(self, lemma: str, created_at: str) -> None:
        self.spellings.add(lemma)
        self.unknown_at = max(self.unknown_at or created_at, created_at)


class _Mark(NamedTuple):
    lemma: str
    mark: str
    created_at: str
    pos: frozenset[str | None]


def upgrade() -> None:
    bind = op.get_bind()
    lemmas = _read_lemmas(bind)
    log: list[str] = []
    marks = [_resolve(lemma, rows, log) for lemma, rows in sorted(lemmas.items())]

    op.create_table(
        "word_marks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lemma", sa.Text(), nullable=False),
        sa.Column("mark", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("lemma", name="uq_word_marks_lemma"),
        sa.CheckConstraint(f"mark IN ('{KNOWN}','{UNKNOWN}')", name="ck_word_marks_mark"),
    )
    op.create_table(
        "known_pos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lemma", sa.Text(), nullable=False),
        sa.Column("pos", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lemma"], ["word_marks.lemma"], ondelete="CASCADE"),
        sa.UniqueConstraint("lemma", "pos", name="uq_known_pos_lemma_pos"),
    )
    op.create_index(
        ANY_POS_INDEX, "known_pos", ["lemma"], unique=True, sqlite_where=sa.text("pos IS NULL"),
    )
    if marks:
        bind.execute(
            sa.text(
                "INSERT INTO word_marks (lemma, mark, created_at)"
                " VALUES (:lemma, :mark, :created_at)",
            ),
            [{"lemma": m.lemma, "mark": m.mark, "created_at": m.created_at} for m in marks],
        )
    pos_rows = [
        {"lemma": m.lemma, "pos": pos}
        for m in marks
        for pos in sorted(m.pos, key=lambda p: p or "")
    ]
    if pos_rows:
        bind.execute(
            sa.text("INSERT INTO known_pos (lemma, pos) VALUES (:lemma, :pos)"), pos_rows,
        )

    op.drop_table("known_words")
    op.drop_table("unknown_words")
    _write_log(bind, log)


def downgrade() -> None:
    msg = "0054 merged the Known and Unknown lists and dropped conflicting marks"
    raise NotImplementedError(msg)


def _read_lemmas(bind: Connection) -> dict[str, _Lemma]:
    lemmas: dict[str, _Lemma] = defaultdict(_Lemma)
    for lemma, pos, created_at in bind.execute(
        sa.text("SELECT lemma, pos, created_at FROM known_words"),
    ):
        lemmas[lemma.lower()].see_known(lemma, pos, str(created_at))
    for lemma, created_at in bind.execute(
        sa.text("SELECT lemma, created_at FROM unknown_words"),
    ):
        lemmas[lemma.lower()].see_unknown(lemma, str(created_at))
    return lemmas


def _resolve(lemma: str, rows: _Lemma, log: list[str]) -> _Mark:
    if len(rows.spellings) > 1:
        log.append(f"case-merge lemma={lemma} spellings={','.join(sorted(rows.spellings))}")
    if rows.known_at is not None and rows.unknown_at is not None:
        kept = KNOWN if rows.known_at > rows.unknown_at else UNKNOWN
        dropped = "" if kept == KNOWN else f" dropped_pos={_pos_list(rows.pos)}"
        log.append(
            f"conflict lemma={lemma} known_at={rows.known_at}"
            f" unknown_at={rows.unknown_at} kept={kept}{dropped}",
        )
        return _mark(lemma, kept, rows, log)
    return _mark(lemma, KNOWN if rows.known_at is not None else UNKNOWN, rows, log)


def _mark(lemma: str, mark: str, rows: _Lemma, log: list[str]) -> _Mark:
    created_at = max(at for at in (rows.known_at, rows.unknown_at) if at is not None)
    if mark == UNKNOWN:
        return _Mark(lemma, mark, created_at, frozenset())
    pos: frozenset[str | None] = frozenset(rows.pos)
    if None in pos and len(pos) > 1:
        dropped = sorted(p for p in pos if p is not None)
        log.append(f"pos-absorbed lemma={lemma} dropped={','.join(dropped)}")
        pos = frozenset({None})
    return _Mark(lemma, mark, created_at, pos)


def _write_log(bind: Connection, lines: list[str]) -> None:
    database = bind.engine.url.database
    if not lines or not database or database == ":memory:":
        return
    path = Path(database).parent / LOG_NAME
    header = f"# {revision} run at {datetime.now(tz=UTC).isoformat(timespec='seconds')}"
    with path.open("a", encoding="utf-8") as log:
        log.writelines(f"{line}\n" for line in (header, *lines))


def _pos_list(pos: set[str | None]) -> str:
    return ",".join(sorted(ANY_POS if p is None else p for p in pos))
