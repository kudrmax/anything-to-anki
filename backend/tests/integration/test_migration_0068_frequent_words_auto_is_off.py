"""Migration 0068 turns a saved Auto frequent word threshold into Off."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0067"
REVISION_UNDER_TEST = "0068"
KEY = "frequent_word_threshold"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _threshold(url: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT value FROM settings WHERE key = :key"), {"key": KEY},
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _store(url: str, value: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
                {"key": KEY, "value": value},
            )
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_a_saved_auto_becomes_off(url: str) -> None:
    _store(url, "auto")

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _threshold(url) == "off"


@pytest.mark.parametrize("saved", ["4.0", "4.5", "5.0", "5.5", "off"])
def test_a_saved_value_stays(url: str, saved: str) -> None:
    _store(url, saved)

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _threshold(url) == saved


def test_no_saved_threshold_stores_nothing(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _threshold(url) is None
