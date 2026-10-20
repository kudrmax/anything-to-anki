"""Migration 0055: the bindings' card choice stays only on orphans; decision conflicts from
before P6 and Unknown marks beside "учу" are resolved and logged (spec §1, §2, §8)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0054"
REVISION_UNDER_TEST = "0055"
LOG_NAME = "migration-0055.log"
HERE, THERE = 101, 102     # past the built-in sources the migrations create
EARLY, LATE = "2026-01-01 00:00:00", "2026-02-01 00:00:00"
SINCE = "2026-09-01 00:00:00"
MARKED_AT = "2026-03-01 00:00:00"

LIVE_WORD = 1                   # glare: Learn in Anki, plus an old released binding
BOUND_LOSER, BOUND_WINNER = 10, 11      # bask: the bound Known wins over a later Learn
EARLY_WORD, LATE_WORD = 20, 21          # cower: studied later wins
LOW_WORD, HIGH_WORD = 30, 31            # Dwell/dwell: same studied_at, the lower id wins
UNKNOWN_LEARN = 40                      # fret: Unknown beside a Learn
LIVE_NOTE, RELEASED_NOTE, BOUND_NOTE, ORPHAN_NOTE, UNKNOWN_ORPHAN_NOTE = 1, 2, 3, 4, 5


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _word(
    conn: Connection, word_id: int, lemma: str, choice: str, *, source_id: int = HERE,
    studied_at: str | None = None,
) -> None:
    insert_word(conn, word_id, source_id=source_id, lemma=lemma, status="learn")
    conn.execute(text("UPDATE phrases SET choice = :c WHERE candidate_id = :w"),
                 {"c": choice, "w": word_id})
    conn.execute(text("UPDATE candidates SET status = :s, studied_at = :at WHERE id = :w"),
                 {"s": "known" if choice == "known" else "learn", "at": studied_at,
                  "w": word_id})


def _binding(
    conn: Connection, note_id: int, lemma: str, choice: str, *, word_id: int | None = None,
    released_at: str | None = None,
) -> None:
    conn.execute(text(
        "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma, pos,"
        " note_kind, card_choice, learning_since, released_at)"
        " VALUES (:w, :p, :n, :l, 'NOUN', 'learn', :c, :since, :released)"
    ), {
        "w": word_id, "p": None if word_id is None else phrase_id_of(word_id), "n": note_id,
        "l": lemma, "c": choice, "since": SINCE, "released": released_at,
    })


def _unknown(conn: Connection, lemma: str) -> None:
    conn.execute(text(
        "INSERT INTO word_marks (lemma, mark, created_at) VALUES (:l, 'unknown', :at)"
    ), {"l": lemma, "at": MARKED_AT})


@pytest.fixture
def migrated(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for source_id in (HERE, THERE):
            insert_source(conn, source_id)  # type: ignore[arg-type]
        _word(conn, LIVE_WORD, "glare", "learn")
        _binding(conn, RELEASED_NOTE, "glare", "learn", word_id=LIVE_WORD, released_at=EARLY)
        _binding(conn, LIVE_NOTE, "glare", "learn", word_id=LIVE_WORD)
        _binding(conn, ORPHAN_NOTE, "drift", "known")

        _word(conn, BOUND_LOSER, "bask", "learn", studied_at=LATE)
        _word(conn, BOUND_WINNER, "bask", "known", source_id=THERE, studied_at=EARLY)
        _binding(conn, BOUND_NOTE, "bask", "known", word_id=BOUND_WINNER)

        _word(conn, EARLY_WORD, "cower", "learn", studied_at=EARLY)
        _word(conn, LATE_WORD, "cower", "known", source_id=THERE, studied_at=LATE)

        _word(conn, HIGH_WORD, "dwell", "cloze", source_id=THERE, studied_at=EARLY)
        _word(conn, LOW_WORD, "Dwell", "learn", studied_at=EARLY)

        _word(conn, UNKNOWN_LEARN, "fret", "learn")
        _unknown(conn, "fret")
        _unknown(conn, "gaze")
        _binding(conn, UNKNOWN_ORPHAN_NOTE, "gaze", "learn")
        _unknown(conn, "hush")
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)
    return engine


def _rows(engine: Engine, sql: str) -> dict[int, tuple[object, ...]]:
    with engine.connect() as conn:
        return {int(row[0]): tuple(row[1:]) for row in conn.execute(text(sql))}


def test_only_orphans_keep_their_card_choice(migrated: Engine) -> None:
    assert _rows(migrated, "SELECT anki_note_id, card_choice FROM anki_synced_cards") == {
        LIVE_NOTE: (None,), RELEASED_NOTE: (None,), BOUND_NOTE: (None,),
        ORPHAN_NOTE: ("known",), UNKNOWN_ORPHAN_NOTE: ("learn",),
    }


def test_the_table_keeps_its_indexes_and_takes_bindings_without_a_choice(
    migrated: Engine,
) -> None:
    with migrated.begin() as conn:
        indexes = {
            str(name) for (name,) in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
                " AND tbl_name = 'anki_synced_cards' AND sql IS NOT NULL"
            ))
        }
        conn.execute(text(
            "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma,"
            " note_kind, learning_since) VALUES (:w, :p, 9, 'glare', 'learn', :since)"
        ), {"w": LOW_WORD, "p": phrase_id_of(LOW_WORD), "since": SINCE})
    assert indexes == {
        "ix_anki_synced_cards_candidate_id", "ix_anki_synced_cards_phrase_id",
        "ix_anki_synced_cards_lemma", "ux_anki_synced_cards_active",
    }
    with pytest.raises(IntegrityError), migrated.begin() as conn:
        conn.execute(text(
            "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma,"
            " note_kind, learning_since) VALUES (:w, :p, 10, 'glare', 'learn', :since)"
        ), {"w": LOW_WORD, "p": phrase_id_of(LOW_WORD), "since": SINCE})


def test_one_decision_per_lemma_stays(migrated: Engine) -> None:
    words = _rows(
        migrated,
        "SELECT c.id, p.choice, c.status, c.studied_at FROM candidates c"
        " JOIN phrases p ON p.candidate_id = c.id",
    )

    assert words[BOUND_WINNER] == ("known", "known", EARLY)
    assert words[BOUND_LOSER] == ("none", "pending", None)
    assert words[LATE_WORD] == ("known", "known", LATE)
    assert words[EARLY_WORD] == ("none", "pending", None)
    assert words[LOW_WORD] == ("learn", "learn", EARLY)
    assert words[HIGH_WORD] == ("none", "pending", None)
    assert words[LIVE_WORD][0] == "learn"


def test_learn_and_an_active_binding_take_the_unknown_mark_off(migrated: Engine) -> None:
    with migrated.connect() as conn:
        marks = {str(lemma) for (lemma,) in conn.execute(text("SELECT lemma FROM word_marks"))}

    assert marks == {"hush"}


def test_every_change_is_logged(migrated: Engine, tmp_path: Path) -> None:
    del migrated
    header, *lines = (tmp_path / LOG_NAME).read_text(encoding="utf-8").splitlines()

    assert header.startswith(f"# {REVISION_UNDER_TEST} run at 20")
    low, high = phrase_id_of(LOW_WORD), phrase_id_of(HIGH_WORD)
    assert lines == [
        f"decision-conflict lemma=bask kept={phrase_id_of(BOUND_WINNER)}(known)"
        f" dropped={phrase_id_of(BOUND_LOSER)}(learn) by=binding",
        f"decision-conflict lemma=cower kept={phrase_id_of(LATE_WORD)}(known)"
        f" dropped={phrase_id_of(EARLY_WORD)}(learn) by=studied_at",
        f"decision-conflict lemma=dwell kept={low}(learn) dropped={high}(cloze) by=id",
        "unknown-removed lemma=fret by=learn",
        "unknown-removed lemma=gaze by=binding",
        "summary decision-conflicts=3 unknown-removed=2 choice-cleared=3 orphans-kept=2",
    ]
