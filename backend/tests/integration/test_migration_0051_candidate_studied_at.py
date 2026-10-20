"""Migration 0051 adds when a word was last marked; old words keep it empty."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0050"
REVISION_UNDER_TEST = "0051"
COLUMN = "studied_at"
SOURCE = 11
WORD = 1


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(url: str) -> dict[str, bool]:
    engine = create_engine(url)
    try:
        return {c["name"]: c["nullable"] for c in inspect(engine).get_columns("candidates")}
    finally:
        engine.dispose()


def _seed_old_word(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sources (id, title, status, created_at, role)"
                " VALUES (:id, 't', 'done', '2026-01-01 00:00:00', 'content')"
            ), {"id": SOURCE})
            conn.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
                " is_sweet_spot, occurrences, status, is_phrasal_verb)"
                " VALUES (:id, :source, 'quill', 'NOUN', 3.0, 0, 1, 'learn', 0)"
            ), {"id": WORD, "source": SOURCE})
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_upgrade_adds_a_nullable_studied_at_left_empty_on_old_words(url: str) -> None:
    assert COLUMN not in _columns(url)
    _seed_old_word(url)

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _columns(url)[COLUMN] is True
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT studied_at FROM candidates")).scalar_one()
    finally:
        engine.dispose()
    assert stored is None


def test_downgrade_drops_the_column(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    command.downgrade(_alembic_config(url), REVISION_BEFORE)

    assert COLUMN not in _columns(url)
