"""Migration 0039 creates the built-in "Saved phrases" source exactly once."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.domain.value_objects.content_type import ContentType
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

REVISION_UNDER_TEST = "0039"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_saved_phrases_source_is_created_once(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_UNDER_TEST)
    command.downgrade(cfg, "0038")
    command.upgrade(cfg, REVISION_UNDER_TEST)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM sources WHERE content_type = 'phrases'"),
        ).scalar()
    assert count == 1
    with Session(engine) as session:
        source = SqlaSourceRepository(session).get_first_by_content_type(ContentType.PHRASES)
    assert source is not None
    assert source.title == "Saved phrases"
    assert source.is_permanent
    assert source.created_at.tzinfo is not None
