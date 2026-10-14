"""Migration 0048 adds unknown words and a card's phrase words, dropping the stale count."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration

STALE_COLUMNS = {"fragment_purity", "fragment_unknown_count"}


def _columns(db_url: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db_url)).get_columns("candidates")}


def test_upgrade_keeps_cards_and_downgrade_restores_columns(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(database.__file__).parent.parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "0047")
    with create_engine(db_url).begin() as conn:
        conn.execute(text(
            "INSERT INTO sources (id, title, status, role, created_at)"
            " VALUES (100, 'title', 'done', 'content', '2026-01-01 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
            " is_sweet_spot, context_fragment, fragment_purity, fragment_unknown_count,"
            " occurrences, status, is_phrasal_verb, has_custom_context_fragment)"
            " VALUES (1, 100, 'feast', 'NOUN', 3.9, 1, 'a feast', 'dirty', 1, 1, 'pending', 0, 0)"
        ))

    command.upgrade(cfg, "0048")
    columns = _columns(db_url)
    assert not columns & STALE_COLUMNS
    assert "phrase_words" in columns
    assert "unknown_words" in inspect(create_engine(db_url)).get_table_names()
    with create_engine(db_url).connect() as conn:
        row = conn.execute(text("SELECT lemma, phrase_words FROM candidates")).one()
    assert tuple(row) == ("feast", None)

    command.downgrade(cfg, "0047")
    assert _columns(db_url) >= STALE_COLUMNS
    assert "unknown_words" not in inspect(create_engine(db_url)).get_table_names()
