"""Migration 0044 gives candidates the positions of their phrase and target."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0043"
REVISION_UNDER_TEST = "0044"
NEW_COLUMNS = {"phrase_position", "target_position"}


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(db_url: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db_url)).get_columns("candidates")}


def test_upgrade_adds_positions_and_downgrade_drops_them(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, REVISION_BEFORE)
    assert not _columns(db_url) & NEW_COLUMNS

    command.upgrade(cfg, REVISION_UNDER_TEST)
    assert _columns(db_url) >= NEW_COLUMNS

    command.downgrade(cfg, REVISION_BEFORE)
    assert not _columns(db_url) & NEW_COLUMNS
