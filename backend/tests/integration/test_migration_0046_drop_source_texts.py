"""Migration 0046 drops the columns sources had before documents."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

OLD_COLUMNS = {"raw_text", "cleaned_text", "input_method", "content_type"}


def _columns(db_url: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db_url)).get_columns("sources")}


def test_upgrade_drops_old_columns_and_downgrade_brings_them_back(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(database.__file__).parent.parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "0046")
    assert not _columns(db_url) & OLD_COLUMNS

    command.downgrade(cfg, "0045")
    assert _columns(db_url) >= OLD_COLUMNS
