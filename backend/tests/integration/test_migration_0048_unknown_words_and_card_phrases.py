"""Migration 0048 adds unknown words and card phrases in place of the old phrase columns.

Its carrying of old cards was applied to prod and dev and then emptied; a new database
only gets the schema.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

OLD_COLUMNS = {
    "fragment_unknown_count", "fragment_purity", "context_fragment", "surface_form",
    "has_custom_context_fragment", "polished_fragment", "target_position",
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_new_database_gets_unknown_words_and_card_phrases(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), "0048")

    inspector = inspect(create_engine(db_url))
    columns = {c["name"]: c for c in inspector.get_columns("candidates")}
    assert "unknown_words" in inspector.get_table_names()
    assert columns["source_phrase"]["nullable"] is False
    assert columns["polished_phrase"]["nullable"] is True
    assert not set(columns) & OLD_COLUMNS
