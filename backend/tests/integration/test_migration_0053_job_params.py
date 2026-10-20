"""Migration 0053 gives jobs params: old jobs keep them empty."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0052"
REVISION_UNDER_TEST = "0053"
COLUMN = "params"
SOURCE = 11


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(url: str) -> dict[str, bool]:
    engine = create_engine(url)
    try:
        return {c["name"]: c["nullable"] for c in inspect(engine).get_columns("jobs")}
    finally:
        engine.dispose()


def _seed_old_job(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sources (id, title, status, created_at, role)"
                " VALUES (:id, 't', 'done', '2026-01-01 00:00:00', 'content')"
            ), {"id": SOURCE})
            conn.execute(text(
                "INSERT INTO jobs (job_type, source_id, status, created_at)"
                " VALUES ('topic_targets', :source, 'queued', '2026-01-01 00:00:00')"
            ), {"source": SOURCE})
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_upgrade_adds_nullable_params_left_empty_on_old_jobs(url: str) -> None:
    assert COLUMN not in _columns(url)
    _seed_old_job(url)

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _columns(url)[COLUMN] is True
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT params FROM jobs")).scalar_one()
    finally:
        engine.dispose()
    assert stored is None


def test_downgrade_drops_the_column(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    command.downgrade(_alembic_config(url), REVISION_BEFORE)

    assert COLUMN not in _columns(url)
