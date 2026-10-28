"""Migration 0066 moves the saved CEFR level one up: it now names the level being learned."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0065"
REVISION_UNDER_TEST = "0066"
KEY = "cefr_level"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _level(url: str) -> str | None:
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


@pytest.mark.parametrize(
    ("saved", "moved"),
    [("A1", "A2"), ("A2", "B1"), ("B1", "B2"), ("B2", "C1"), ("C1", "C2"), ("C2", "C2")],
)
def test_the_saved_level_moves_one_up(url: str, saved: str, moved: str) -> None:
    _store(url, saved)

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _level(url) == moved


def test_a_lowercase_level_moves_too(url: str) -> None:
    _store(url, "b1")

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _level(url) == "B2"


def test_no_saved_level_stores_nothing(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _level(url) is None


def test_downgrade_moves_the_level_back(url: str) -> None:
    _store(url, "B1")
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    command.downgrade(_alembic_config(url), REVISION_BEFORE)

    assert _level(url) == "B1"
