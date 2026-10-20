"""Migration 0054 merges the Known and Unknown lists into one mark per lemma (spec §8)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0052"
REVISION_UNDER_TEST = "0054"
LOG_NAME = "migration-0054.log"

KNOWN_ROWS: tuple[tuple[str, str | None, str], ...] = (
    ("Glare", "VERB", "2026-01-01 00:00:00"),     # case-merge with glare
    ("glare", "NOUN", "2026-03-01 00:00:00.5"),
    ("abide", None, "2026-01-01 00:00:00"),       # any pos absorbs VERB and NOUN
    ("abide", "VERB", "2026-02-01 00:00:00"),
    ("Abide", "NOUN", "2026-01-15 00:00:00"),
    ("bask", "VERB", "2026-05-01 00:00:00"),      # known later than unknown: stays known
    ("cower", "VERB", "2026-01-01 00:00:00"),     # unknown later: becomes unknown
    ("dwell", "VERB", "2026-04-01 00:00:00"),     # tie: unknown
    ("evade", "ADJ", "2026-01-01 00:00:00"),      # untouched
)
UNKNOWN_ROWS: tuple[tuple[str, str], ...] = (
    ("bask", "2026-04-01 00:00:00"),
    ("cower", "2026-06-01 00:00:00"),
    ("dwell", "2026-04-01 00:00:00"),
    ("fret", "2026-02-01 00:00:00"),
)


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def migrated(tmp_path: Path) -> Engine:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for lemma, pos, at in KNOWN_ROWS:
            conn.execute(text(
                "INSERT INTO known_words (lemma, pos, created_at) VALUES (:l, :p, :at)"
            ), {"l": lemma, "p": pos, "at": at})
        for lemma, at in UNKNOWN_ROWS:
            conn.execute(text(
                "INSERT INTO unknown_words (lemma, created_at) VALUES (:l, :at)"
            ), {"l": lemma, "at": at})
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)
    return engine


def _marks(engine: Engine) -> dict[str, tuple[str, str]]:
    with engine.connect() as conn:
        return {
            str(lemma): (str(mark), str(at)) for lemma, mark, at in conn.execute(
                text("SELECT lemma, mark, created_at FROM word_marks"),
            )
        }


def _pos(engine: Engine) -> set[tuple[str, str | None]]:
    with engine.connect() as conn:
        return {
            (str(lemma), pos)
            for lemma, pos in conn.execute(text("SELECT lemma, pos FROM known_pos"))
        }


def test_the_lists_merge_into_one_mark_per_lower_case_lemma(migrated: Engine) -> None:
    assert _marks(migrated) == {
        "glare": ("known", "2026-03-01 00:00:00.5"),
        "abide": ("known", "2026-02-01 00:00:00"),
        "bask": ("known", "2026-05-01 00:00:00"),
        "cower": ("unknown", "2026-06-01 00:00:00"),
        "dwell": ("unknown", "2026-04-01 00:00:00"),
        "evade": ("known", "2026-01-01 00:00:00"),
        "fret": ("unknown", "2026-02-01 00:00:00"),
    }


def test_known_keeps_its_parts_of_speech_and_any_pos_absorbs_the_others(
    migrated: Engine,
) -> None:
    assert _pos(migrated) == {
        ("glare", "VERB"), ("glare", "NOUN"), ("abide", None), ("bask", "VERB"),
        ("evade", "ADJ"),
    }


def test_every_case_merge_conflict_and_absorbed_pos_is_logged(
    migrated: Engine, tmp_path: Path,
) -> None:
    del migrated
    lines = (tmp_path / LOG_NAME).read_text(encoding="utf-8").splitlines()

    assert sorted(lines) == sorted([
        "case-merge lemma=abide spellings=Abide,abide",
        "pos-absorbed lemma=abide dropped=NOUN,VERB",
        "conflict lemma=bask known_at=2026-05-01 00:00:00"
        " unknown_at=2026-04-01 00:00:00 kept=known",
        "conflict lemma=cower known_at=2026-01-01 00:00:00"
        " unknown_at=2026-06-01 00:00:00 kept=unknown",
        "conflict lemma=dwell known_at=2026-04-01 00:00:00"
        " unknown_at=2026-04-01 00:00:00 kept=unknown",
        "case-merge lemma=glare spellings=Glare,glare",
    ])


def test_the_old_tables_go_and_the_new_ones_hold_the_rules(migrated: Engine) -> None:
    inspector = inspect(migrated)
    tables = set(inspector.get_table_names())
    assert {"word_marks", "known_pos"} <= tables
    assert not {"known_words", "unknown_words"} & tables
    assert inspector.get_pk_constraint("word_marks")["constrained_columns"] == ["id"]
    assert inspector.get_pk_constraint("known_pos")["constrained_columns"] == ["id"]
    assert [u["column_names"] for u in inspector.get_unique_constraints("word_marks")] == [
        ["lemma"],
    ]
    assert [u["column_names"] for u in inspector.get_unique_constraints("known_pos")] == [
        ["lemma", "pos"],
    ]
    [fk] = inspector.get_foreign_keys("known_pos")
    assert (fk["referred_table"], fk["options"].get("ondelete")) == ("word_marks", "CASCADE")
    with migrated.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.execute(text("DELETE FROM word_marks WHERE lemma = 'glare'"))
        assert conn.execute(
            text("SELECT count(*) FROM known_pos WHERE lemma = 'glare'"),
        ).scalar_one() == 0


def test_a_mark_other_than_known_or_unknown_is_refused(migrated: Engine) -> None:
    with pytest.raises(IntegrityError, match="CHECK constraint"), migrated.begin() as conn:
        conn.execute(text(
            "INSERT INTO word_marks (lemma, mark, created_at) VALUES ('x', 'maybe', '2026')"
        ))


def test_downgrade_is_refused(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)

    with pytest.raises(NotImplementedError):
        command.downgrade(_alembic_config(db_url), REVISION_BEFORE)


def test_an_empty_database_writes_no_log(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)

    assert not (tmp_path / LOG_NAME).exists()


def test_ids_survive_a_vacuum(migrated: Engine) -> None:
    query = (
        "SELECT 'mark', id, lemma, NULL FROM word_marks"
        " UNION ALL SELECT 'pos', id, lemma, pos FROM known_pos"
    )
    with migrated.begin() as conn:
        conn.execute(text("DELETE FROM known_pos WHERE lemma = 'glare' AND pos = 'VERB'"))
        conn.execute(text("DELETE FROM word_marks WHERE lemma = 'abide'"))
        conn.execute(text("DELETE FROM known_pos WHERE lemma = 'abide'"))
        before = set(conn.execute(text(query)).all())
    with migrated.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT").exec_driver_sql("VACUUM")
    with migrated.connect() as conn:
        assert set(conn.execute(text(query)).all()) == before
