"""Migration 0067 moves every user to the new default card layout: a saved layout is dropped."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0066"
REVISION_UNDER_TEST = "0067"
KEY = "card_layout"
OTHER_KEY = "cefr_level"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _value(url: str, key: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT value FROM settings WHERE key = :key"), {"key": key},
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _store(url: str, key: str, value: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
                {"key": key, "value": value},
            )
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_a_saved_layout_gives_way_to_the_default(url: str) -> None:
    _store(url, KEY, '{"columns": [], "styles": []}')
    _store(url, OTHER_KEY, "B1")

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _value(url, KEY) is None
    assert _value(url, OTHER_KEY) == "B1"


def test_no_saved_layout_stays_so(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _value(url, KEY) is None
