"""Migration 0057 drops `candidates.status` and puts the lemma index back without it; 0058
gives the projection its last time tick (spec §2, §5)."""
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

REVISION_BEFORE = "0056"
DROP_STATUS = "0057"
TICKED_AT = "0058"
WORD = 7
SOURCE = 50


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """At 0056, with one word that stores a status."""
    url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(url), REVISION_BEFORE)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sources (id, title, status, created_at)"
            " VALUES (:id, 'Book', 'done', '2026-01-01 00:00:00')"
        ), {"id": SOURCE})
        conn.execute(text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, status, is_phrasal_verb)"
            " VALUES (:id, :source, 'Glare', 'VERB', 3.1, 1, 2, 'learn', 0)"
        ), {"id": WORD, "source": SOURCE})
    engine.dispose()
    return url


def _migrated(db_url: str, revision: str) -> Engine:
    command.upgrade(_alembic_config(db_url), revision)
    return create_engine(db_url)


def test_the_status_column_goes_and_the_word_stays(db_url: str) -> None:
    engine = _migrated(db_url, DROP_STATUS)

    assert "status" not in {c["name"] for c in inspect(engine).get_columns("candidates")}
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT id, lemma, pos, zipf_frequency, is_sweet_spot, occurrences FROM candidates",
        )).all() == [(WORD, "Glare", "VERB", 3.1, 1, 2)]


def test_the_lemma_index_is_on_the_lower_case_lemma_alone(db_url: str) -> None:
    engine = _migrated(db_url, DROP_STATUS)

    with engine.connect() as conn:
        sql = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE name = 'ix_candidates_lower_lemma'",
        )).scalar_one()
        plan = " ".join(str(row[-1]) for row in conn.execute(text(
            "EXPLAIN QUERY PLAN SELECT id FROM candidates WHERE lower(lemma) = 'glare'",
        )))
    assert "lower(lemma)" in sql
    assert "status" not in sql
    assert "ix_candidates_lower_lemma" in plan


def test_the_drop_cannot_be_undone(db_url: str) -> None:
    _migrated(db_url, DROP_STATUS)

    with pytest.raises(NotImplementedError):
        command.downgrade(_alembic_config(db_url), REVISION_BEFORE)


def test_the_projection_gets_an_empty_last_tick(db_url: str) -> None:
    engine = _migrated(db_url, TICKED_AT)

    columns = {c["name"]: c for c in inspect(engine).get_columns("projection_meta")}
    assert list(columns) == ["id", "revision", "ticked_at"]
    assert columns["ticked_at"]["nullable"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT ticked_at FROM projection_meta")).all() == [(None,)]

    command.downgrade(_alembic_config(db_url), DROP_STATUS)
    assert "ticked_at" not in {c["name"] for c in inspect(engine).get_columns("projection_meta")}
