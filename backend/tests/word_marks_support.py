"""Known and Unknown marks written to and read from the tables directly."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

LONG_AGO = "2026-01-01 00:00:00"


def insert_known(
    session: Session, lemma: str, *pos: str | None, created_at: str = LONG_AGO,
) -> None:
    """The lemma marked Known in each given pos (none given: any pos)."""
    session.execute(
        text(
            "INSERT OR IGNORE INTO word_marks (lemma, mark, created_at)"
            " VALUES (:lemma, 'known', :at)"
        ),
        {"lemma": lemma.lower(), "at": created_at},
    )
    for one in pos or (None,):
        session.execute(
            text("INSERT INTO known_pos (lemma, pos) VALUES (:lemma, :pos)"),
            {"lemma": lemma.lower(), "pos": one},
        )


def insert_unknown(session: Session, lemma: str, *, created_at: str = LONG_AGO) -> None:
    session.execute(
        text(
            "INSERT INTO word_marks (lemma, mark, created_at)"
            " VALUES (:lemma, 'unknown', :at)"
        ),
        {"lemma": lemma.lower(), "at": created_at},
    )


def known_rows(session: Session) -> set[tuple[str, str | None]]:
    return {
        (str(lemma), pos) for lemma, pos in session.execute(text(
            "SELECT p.lemma, p.pos FROM known_pos p"
            " JOIN word_marks m ON m.lemma = p.lemma WHERE m.mark = 'known'"
        ))
    }


def unknown_lemmas(session: Session) -> set[str]:
    return {
        str(lemma) for (lemma,) in session.execute(
            text("SELECT lemma FROM word_marks WHERE mark = 'unknown'"),
        )
    }
