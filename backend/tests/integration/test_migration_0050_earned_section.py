"""Migration 0050 adds the section a phrase earned; old phrases keep it empty."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.models import dump_phrase
from sqlalchemy import create_engine, inspect, text

from tests.phrase_support import phrase

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0049"
REVISION_UNDER_TEST = "0050"
COLUMN = "earned_section"
SOURCE = 11
WORD = 1
PHRASE = 1


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _columns(url: str) -> dict[str, bool]:
    engine = create_engine(url)
    try:
        return {c["name"]: c["nullable"] for c in inspect(engine).get_columns("phrases")}
    finally:
        engine.dispose()


def _seed_old_phrase(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sources (id, title, status, created_at, role)"
                " VALUES (:id, 't', 'done', '2026-01-01 00:00:00', 'content')"
            ), {"id": SOURCE})
            conn.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
                " is_sweet_spot, occurrences, status, is_phrasal_verb)"
                " VALUES (:id, :source, 'quill', 'NOUN', 3.0, 0, 1, 'pending', 0)"
            ), {"id": WORD, "source": SOURCE})
            conn.execute(text(
                "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
                " created_at) VALUES (:id, :word, :phrase, 'auto', 'selection', 'none',"
                " '2026-01-01 00:00:00')"
            ), {"id": PHRASE, "word": WORD, "phrase": dump_phrase(phrase("a quill", "quill"))})
    finally:
        engine.dispose()


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    return db_url


def test_upgrade_adds_a_nullable_earned_section_left_empty_on_old_phrases(url: str) -> None:
    assert COLUMN not in _columns(url)
    _seed_old_phrase(url)

    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    assert _columns(url)[COLUMN] is True
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            stored = conn.execute(text("SELECT earned_section FROM phrases")).scalar_one()
    finally:
        engine.dispose()
    assert stored is None


def test_downgrade_drops_the_column(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    command.downgrade(_alembic_config(url), REVISION_BEFORE)

    assert COLUMN not in _columns(url)
