"""Migration 0056 creates the empty tables of the card state projection (spec §5)."""
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

REVISION_BEFORE = "0055"
REVISION_UNDER_TEST = "0056"
PROJECTION_TABLES = ("card_states", "word_states", "phrase_words", "projection_meta")


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
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)
    return create_engine(db_url)


def _sql(engine: Engine, kind: str, name: str) -> str:
    with engine.connect() as conn:
        return str(conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = :kind AND name = :name"),
            {"kind": kind, "name": name},
        ).scalar_one())


def test_the_tables_have_their_columns(migrated: Engine) -> None:
    columns = {
        table: {c["name"]: c for c in inspect(migrated).get_columns(table)}
        for table in PROJECTION_TABLES
    }
    assert list(columns["card_states"]) == [
        "phrase_id", "source_id", "word_id", "lemma", "is_done", "wants_generation",
        "sections", "new_counts", "changes_at", "revision", "removed",
    ]
    assert [name for name, c in columns["card_states"].items() if c["nullable"]] == [
        "changes_at",
    ]
    assert list(columns["word_states"]) == ["word_id", "source_id", "lemma", "status"]
    assert list(columns["phrase_words"]) == [
        "lemma", "phrase_id", "position", "zipf", "content", "level", "newness",
    ]
    assert list(columns["projection_meta"]) == ["id", "revision"]


def test_the_keys_and_indexes(migrated: Engine) -> None:
    inspector = inspect(migrated)
    assert inspector.get_pk_constraint("card_states")["constrained_columns"] == ["phrase_id"]
    assert inspector.get_pk_constraint("word_states")["constrained_columns"] == ["word_id"]
    assert inspector.get_pk_constraint("phrase_words")["constrained_columns"] == [
        "phrase_id", "position",
    ]
    assert "WITHOUT ROWID" in _sql(migrated, "table", "phrase_words")
    indexes = {
        table: {i["name"]: i["column_names"] for i in inspector.get_indexes(table)}
        for table in PROJECTION_TABLES
    }
    assert indexes["card_states"] == {
        "ix_card_states_source_removed_done": ["source_id", "removed", "is_done"],
        "ix_card_states_source_revision": ["source_id", "revision"],
        "ix_card_states_lemma": ["lemma"],
        "ix_card_states_word_id": ["word_id"],
        "ix_card_states_changes_at": ["changes_at"],
    }
    assert "WHERE changes_at IS NOT NULL" in _sql(migrated, "index", "ix_card_states_changes_at")
    assert indexes["word_states"] == {
        "ix_word_states_source_id": ["source_id"], "ix_word_states_lemma": ["lemma"],
    }
    assert indexes["phrase_words"] == {"ix_phrase_words_lemma": ["lemma"]}
    assert all(not inspector.get_foreign_keys(table) for table in PROJECTION_TABLES)


def test_the_tables_start_empty_and_the_revision_at_zero(migrated: Engine) -> None:
    with migrated.connect() as conn:
        for table in ("card_states", "word_states", "phrase_words"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0  # noqa: S608
        assert conn.execute(text("SELECT id, revision FROM projection_meta")).all() == [(1, 0)]


def test_the_meta_table_holds_one_row(migrated: Engine) -> None:
    with pytest.raises(IntegrityError), migrated.begin() as conn:
        conn.execute(text("INSERT INTO projection_meta (id, revision) VALUES (2, 0)"))


def test_a_card_row_is_live_unless_said_removed(migrated: Engine) -> None:
    with migrated.begin() as conn:
        conn.execute(text(
            "INSERT INTO card_states (phrase_id, source_id, word_id, lemma, is_done,"
            " wants_generation, sections, new_counts, revision)"
            " VALUES (1, 1, 1, 'glare', 0, 0, 'RRRRRRRR', '0,0,0,0,0,0,0,0', 1)"
        ))
        assert conn.execute(text("SELECT removed FROM card_states")).scalar_one() == 0


def test_downgrade_drops_the_tables(migrated: Engine, tmp_path: Path) -> None:
    command.downgrade(_alembic_config(f"sqlite:///{tmp_path / 'app.db'}"), REVISION_BEFORE)
    names = set(inspect(create_engine(f"sqlite:///{tmp_path / 'app.db'}")).get_table_names())
    assert not names & set(PROJECTION_TABLES)
