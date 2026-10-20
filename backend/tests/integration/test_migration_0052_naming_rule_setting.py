"""Migration 0052 turns the chapter titles template into the default naming rule."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0051"
REVISION_UNDER_TEST = "0052"
OLD_KEY = "book_chapter_title_template"
NEW_KEY = "naming_rule"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _settings(url: str) -> dict[str, str]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT key, value FROM settings")).all()
        return {key: value for key, value in rows if key in (OLD_KEY, NEW_KEY)}
    finally:
        engine.dispose()


def _store(url: str, value: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
                {"key": OLD_KEY, "value": value},
            )
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_default_template_becomes_collection_rule(url: str) -> None:
    _store(url, "{{book_name}} ch{{n}}")

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _settings(url) == {NEW_KEY: "{{collection}} ch{{n}}"}


def test_chapter_title_becomes_title(url: str) -> None:
    _store(url, "{{chapter_title}} ({{book_name}})")

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _settings(url) == {NEW_KEY: "{{title}} ({{collection}})"}


def test_no_stored_template_stores_nothing(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _settings(url) == {}


def test_downgrade_restores_the_template(url: str) -> None:
    _store(url, "{{n}}. {{chapter_title}} ({{book_name}})")
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    command.downgrade(_alembic_config(url), REVISION_BEFORE)

    assert _settings(url) == {OLD_KEY: "{{n}}. {{chapter_title}} ({{book_name}})"}
