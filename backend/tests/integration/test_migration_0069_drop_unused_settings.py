"""Migration 0069 drops the settings nothing reads and keeps the others."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0068"
REVISION_UNDER_TEST = "0069"
STORED = (("ai_provider", "claude"), ("enable_definitions", "true"), ("ai_model", "opus"))


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _keys(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return set(conn.execute(text("SELECT key FROM settings")).scalars())
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for key, value in STORED:
                conn.execute(
                    text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
                    {"key": key, "value": value},
                )
    finally:
        engine.dispose()
    return db_url


def test_the_unused_settings_go_and_the_others_stay(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    keys = _keys(url)
    assert "ai_provider" not in keys
    assert "enable_definitions" not in keys
    assert "ai_model" in keys
