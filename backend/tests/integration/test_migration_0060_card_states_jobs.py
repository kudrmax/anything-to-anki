"""Migration 0060 adds what the queue holds for each card to card_states and to the covering
index of the ✨ counts; stored rows get no job until the start's rebuild."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0059"
REVISION_UNDER_TEST = "0060"
JOBS = ("polish_job", "meaning_job", "media_job", "tts_job", "pronunciation_job")
GENERATION = [
    "source_id", "removed", "wants_generation", "open_sections", "polish_done",
    "meaning_done", "media_done", "tts_done", "pronunciation_done", "media_timed",
]


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(url), REVISION_BEFORE)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO card_states (phrase_id, source_id, word_id, lemma, is_done,"
            " wants_generation, sections, open_sections, new_counts, revision, removed)"
            " VALUES (1, 1, 1, 'glare', 0, 1, 'RRRRRRRR', 'RRRRRRRR', '0,0,0,0,0,0,0,0', 1, 0)"
        ))
    engine.dispose()
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)
    return url


@pytest.fixture
def migrated(db_url: str) -> Engine:
    return create_engine(db_url)


def test_a_stored_row_gets_no_job(migrated: Engine) -> None:
    with migrated.connect() as conn:
        row = conn.execute(text(
            f"SELECT {', '.join(JOBS)} FROM card_states",  # noqa: S608 — test names
        )).one()
    assert tuple(row) == tuple(0 for _ in JOBS)


def test_the_generation_index_covers_the_jobs(migrated: Engine) -> None:
    indexes = {i["name"]: i["column_names"] for i in inspect(migrated).get_indexes("card_states")}
    assert indexes["ix_card_states_generation"] == [*GENERATION, *JOBS]


def test_downgrade_drops_them(db_url: str) -> None:
    command.downgrade(_alembic_config(db_url), REVISION_BEFORE)
    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert not set(JOBS) & {c["name"] for c in inspector.get_columns("card_states")}
    indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("card_states")}
    assert indexes["ix_card_states_generation"] == GENERATION
