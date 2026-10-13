"""Migration 0042 creates source_documents (1:1 with sources, cascade delete)."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0041"
REVISION_UNDER_TEST = "0042"
TABLE = "source_documents"
EXPECTED_COLUMNS = {"source_id", "document"}


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_upgrade_creates_table_and_downgrade_drops_it(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    engine = create_engine(db_url)

    command.upgrade(cfg, REVISION_BEFORE)
    assert TABLE not in inspect(engine).get_table_names()

    command.upgrade(cfg, REVISION_UNDER_TEST)
    inspector = inspect(engine)
    assert TABLE in inspector.get_table_names()
    assert {c["name"] for c in inspector.get_columns(TABLE)} == EXPECTED_COLUMNS
    assert inspector.get_pk_constraint(TABLE)["constrained_columns"] == ["source_id"]
    foreign_keys = inspector.get_foreign_keys(TABLE)
    assert [(fk["referred_table"], fk["options"].get("ondelete")) for fk in foreign_keys] == [
        ("sources", "CASCADE"),
    ]

    command.downgrade(cfg, REVISION_BEFORE)
    assert TABLE not in inspect(engine).get_table_names()
