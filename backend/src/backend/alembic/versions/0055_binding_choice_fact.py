"""The binding's card choice becomes a fact written once, when its card or source goes:
NULL on every binding whose card lives, kept on the orphans. The decision conflicts left
from before rule P6 are resolved first (spec §1, §8).

Revision ID: 0055
Revises: 0054

- Two or more decision cards (learn/cloze/known) of one lower-case lemma across sources:
  the card with an active binding wins, else the one whose word was studied later, else
  the lower phrase id. Every other one becomes `none`; its word's stored status follows
  (`pending`), its studied_at goes when no card of the word is marked any more, and its
  active binding is released (an active binding belongs to the decision card only, A1/A2).
  The lemma's mark follows the winner: a Learn or Cloze winner takes a Known mark off (else
  it would read Known by the list, Q15); a Known winner keeps or gets the Known mark (AK).
- An Unknown mark beside a Learn or Cloze decision or an active binding of the lemma (its
  timer running or due): "учу" wins, the mark goes.

Each change goes to migration-0055.log beside the database file, after a header line
naming the run, and a summary line with the counts ends the run.
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

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

LOG_NAME = "migration-0055.log"
TABLE = "anki_synced_cards"
NEW_TABLE = "anki_synced_cards_0055"
NO_CHOICE = "none"
NEW_STATUS = "pending"
UNKNOWN = "unknown"
KNOWN = "known"
BY_BINDING = "binding"
BY_STUDIED_AT = "studied_at"
BY_ID = "id"
COLUMNS = (
    "id, candidate_id, phrase_id, anki_note_id, lemma, pos, note_kind, card_choice,"
    " learning_since, released_at"
)


class _Decision(NamedTuple):
    phrase_id: int
    word_id: int
    pos: str | None
    choice: str
    studied_at: str | None
    bound: bool


def upgrade() -> None:
    bind = op.get_bind()
    log: list[str] = []
    _one_decision_per_lemma(bind, log, _now())
    _learn_beats_unknown(bind, log)
    log.append(_summary(bind, log))
    _choice_only_on_orphans()
    _write_log(bind, log)


def downgrade() -> None:
    msg = "0055 dropped the card choice of live bindings and resolved decision conflicts"
    raise NotImplementedError(msg)


def _now() -> str:
    return datetime.now(tz=UTC).replace(tzinfo=None).isoformat(sep=" ")


def _one_decision_per_lemma(bind: Connection, log: list[str], now: str) -> None:
    by_lemma: dict[str, list[_Decision]] = defaultdict(list)
    for lemma, phrase_id, word_id, pos, choice, studied_at, bound in bind.execute(sa.text(
        "SELECT lower(c.lemma), p.id, c.id, c.pos, p.choice, c.studied_at,"
        f" EXISTS (SELECT 1 FROM {TABLE} a"
        "  WHERE a.phrase_id = p.id AND a.released_at IS NULL)"
        " FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE p.choice IN ('learn', 'cloze', 'known')"
    )):
        studied = None if studied_at is None else str(studied_at)
        by_lemma[str(lemma)].append(
            _Decision(phrase_id, word_id, pos, choice, studied, bool(bound)),
        )
    for lemma, decisions in sorted(by_lemma.items()):
        if len(decisions) < 2:  # noqa: PLR2004 — one decision is no conflict
            continue
        winner, *losers = _ranked(decisions)
        for loser in losers:
            _drop(bind, loser)
            released = "".join(
                f" released_binding={binding_id}" for binding_id in _release(bind, loser, now)
            )
            log.append(
                f"decision-conflict lemma={lemma} kept={winner.phrase_id}({winner.choice})"
                f" dropped={loser.phrase_id}({loser.choice}) by={_why(winner, loser)}{released}",
            )
        _mark_follows(bind, lemma, winner, now, log)


def _ranked(decisions: list[_Decision]) -> list[_Decision]:
    """Bound first, then studied later (never studied last), then the lower phrase id."""
    ranked = sorted(decisions, key=lambda d: d.phrase_id)
    ranked.sort(key=lambda d: d.studied_at or "", reverse=True)
    ranked.sort(key=lambda d: not d.bound)
    return ranked


def _why(winner: _Decision, loser: _Decision) -> str:
    if winner.bound != loser.bound:
        return BY_BINDING
    if winner.studied_at != loser.studied_at:
        return BY_STUDIED_AT
    return BY_ID


def _drop(bind: Connection, loser: _Decision) -> None:
    bind.execute(
        sa.text("UPDATE phrases SET choice = :none WHERE id = :p"),
        {"none": NO_CHOICE, "p": loser.phrase_id},
    )
    bind.execute(
        sa.text("UPDATE candidates SET status = :new WHERE id = :w"),
        {"new": NEW_STATUS, "w": loser.word_id},
    )
    bind.execute(
        sa.text(
            "UPDATE candidates SET studied_at = NULL WHERE id = :w AND NOT EXISTS"
            " (SELECT 1 FROM phrases WHERE candidate_id = :w AND choice <> :none)"
        ),
        {"w": loser.word_id, "none": NO_CHOICE},
    )


def _release(bind: Connection, loser: _Decision, now: str) -> list[int]:
    active = f"FROM {TABLE} WHERE phrase_id = :p AND released_at IS NULL"
    ids = [int(i) for (i,) in bind.execute(
        sa.text(f"SELECT id {active} ORDER BY id"), {"p": loser.phrase_id},  # noqa: S608
    )]
    if ids:
        bind.execute(
            sa.text(f"UPDATE {TABLE} SET released_at = :now"  # noqa: S608
                    " WHERE phrase_id = :p AND released_at IS NULL"),
            {"now": now, "p": loser.phrase_id},
        )
    return ids


def _mark_follows(
    bind: Connection, lemma: str, winner: _Decision, now: str, log: list[str],
) -> None:
    mark = bind.execute(
        sa.text("SELECT mark FROM word_marks WHERE lemma = :l"), {"l": lemma},
    ).scalar_one_or_none()
    kept = f"{winner.phrase_id}({winner.choice})"
    if winner.choice != KNOWN:
        if mark == KNOWN:
            bind.execute(sa.text("DELETE FROM known_pos WHERE lemma = :l"), {"l": lemma})
            bind.execute(sa.text("DELETE FROM word_marks WHERE lemma = :l"), {"l": lemma})
            log.append(f"known-removed lemma={lemma} kept={kept}")
        return
    if mark == KNOWN:
        return
    if mark is None:
        bind.execute(
            sa.text("INSERT INTO word_marks (lemma, mark, created_at) VALUES (:l, :k, :now)"),
            {"l": lemma, "k": KNOWN, "now": now},
        )
    else:
        bind.execute(
            sa.text("UPDATE word_marks SET mark = :k, created_at = :now WHERE lemma = :l"),
            {"l": lemma, "k": KNOWN, "now": now},
        )
    bind.execute(
        sa.text("INSERT INTO known_pos (lemma, pos) VALUES (:l, :p)"),
        {"l": lemma, "p": winner.pos},
    )
    log.append(f"known-added lemma={lemma} kept={kept} was={mark or 'none'}")


def _learn_beats_unknown(bind: Connection, log: list[str]) -> None:
    rows = bind.execute(sa.text(
        "SELECT m.lemma,"
        " EXISTS (SELECT 1 FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        "  WHERE lower(c.lemma) = m.lemma AND p.choice IN ('learn', 'cloze')),"
        f" EXISTS (SELECT 1 FROM {TABLE} a"
        "  WHERE lower(a.lemma) = m.lemma AND a.released_at IS NULL)"
        " FROM word_marks m WHERE m.mark = :unknown ORDER BY m.lemma"
    ), {"unknown": UNKNOWN}).all()
    for lemma, learns, bound in rows:
        reasons = [name for name, found in (("learn", learns), (BY_BINDING, bound)) if found]
        if not reasons:
            continue
        bind.execute(sa.text("DELETE FROM word_marks WHERE lemma = :l"), {"l": lemma})
        log.append(f"unknown-removed lemma={lemma} by={','.join(reasons)}")


def _summary(bind: Connection, log: list[str]) -> str:
    live, orphans = bind.execute(sa.text(
        f"SELECT count(phrase_id), count(*) - count(phrase_id) FROM {TABLE}"  # noqa: S608
    )).one()
    conflicts = sum(line.startswith("decision-conflict") for line in log)
    released = sum(line.count(" released_binding=") for line in log)
    known_removed = sum(line.startswith("known-removed") for line in log)
    known_added = sum(line.startswith("known-added") for line in log)
    unknown = sum(line.startswith("unknown-removed") for line in log)
    return (
        f"summary decision-conflicts={conflicts} bindings-released={released}"
        f" known-removed={known_removed} known-added={known_added}"
        f" unknown-removed={unknown} choice-cleared={live} orphans-kept={orphans}"
    )


def _choice_only_on_orphans() -> None:
    """SQLite cannot drop NOT NULL in place: the table is built again, with its indexes."""
    op.create_table(
        NEW_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id", sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "phrase_id", sa.Integer(),
            sa.ForeignKey("phrases.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("anki_note_id", sa.Integer(), nullable=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=True),
        sa.Column("note_kind", sa.String(10), nullable=False),
        sa.Column("card_choice", sa.String(10), nullable=True),
        sa.Column("learning_since", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        f"INSERT INTO {NEW_TABLE} ({COLUMNS})"  # noqa: S608 — constant names
        " SELECT id, candidate_id, phrase_id, anki_note_id, lemma, pos, note_kind,"
        " CASE WHEN phrase_id IS NULL THEN card_choice END, learning_since, released_at"
        f" FROM {TABLE}"
    )
    op.drop_table(TABLE)
    op.rename_table(NEW_TABLE, TABLE)
    op.create_index("ix_anki_synced_cards_candidate_id", TABLE, ["candidate_id"])
    op.create_index("ix_anki_synced_cards_phrase_id", TABLE, ["phrase_id"])
    op.create_index("ix_anki_synced_cards_lemma", TABLE, [sa.text("lower(lemma)")])
    op.create_index(
        "ux_anki_synced_cards_active", TABLE, ["phrase_id"],
        unique=True, sqlite_where=sa.text("released_at IS NULL AND phrase_id IS NOT NULL"),
    )


def _write_log(bind: Connection, lines: list[str]) -> None:
    database = bind.engine.url.database
    if not database or database == ":memory:":
        return
    path = Path(database).parent / LOG_NAME
    header = f"# {revision} run at {datetime.now(tz=UTC).isoformat(timespec='seconds')}"
    with path.open("a", encoding="utf-8") as log:
        log.writelines(f"{line}\n" for line in (header, *lines))
