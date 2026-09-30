"""Migration 0024 gives replacement candidates the CEFR breakdown they lost.

Runs the real Alembic chain on a file-based SQLite DB: up to 0023, seed the
broken state, then upgrade to 0024.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0023"
REVISION_UNDER_TEST = "0024"
SOURCE_ID = 1
ORIGINAL_ID = 10
REPLACEMENT_ID = 11
PHRASAL_VERB_ID = 12
UNRELATED_REPLACEMENT_ID = 13
USAGE_JSON = '{"informal": 1.0}'


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _insert_candidate(
    conn: Connection,
    candidate_id: int,
    lemma: str,
    *,
    status: str,
    is_phrasal_verb: bool = False,
    has_custom_context_fragment: bool = False,
    usage_distribution: str | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
            " is_sweet_spot, context_fragment, fragment_purity, occurrences, status,"
            " is_phrasal_verb, has_custom_context_fragment, usage_distribution)"
            " VALUES (:id, :source_id, :lemma, 'NOUN', 4.0, 1, 'ctx', 'clean', 1, :status,"
            " :pv, :custom, :usage)"
        ),
        {
            "id": candidate_id,
            "source_id": SOURCE_ID,
            "lemma": lemma,
            "status": status,
            "pv": is_phrasal_verb,
            "custom": has_custom_context_fragment,
            "usage": usage_distribution,
        },
    )


@pytest.fixture
def engine_before_migration(tmp_path: Path) -> tuple[Engine, Config]:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_BEFORE)

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sources (id, raw_text, title, status, input_method,"
                " content_type, created_at)"
                " VALUES (:id, 'text', 'title', 'done', 'text_pasted', 'text',"
                " '2026-01-01 00:00:00')"
            ),
            {"id": SOURCE_ID},
        )
        _insert_candidate(
            conn, ORIGINAL_ID, "advance", status="skip", usage_distribution=USAGE_JSON,
        )
        conn.execute(
            text(
                "INSERT INTO cefr_breakdowns (candidate_id, decision_method, cambridge,"
                " cefrpy, efllex_distribution, oxford, kelly)"
                " VALUES (:cid, 'priority', 'B2', 'B1', '{\"B1\": 1.0}', 'B1', NULL)"
            ),
            {"cid": ORIGINAL_ID},
        )
        _insert_candidate(
            conn, REPLACEMENT_ID, "advance", status="pending",
            has_custom_context_fragment=True,
        )
        _insert_candidate(
            conn, PHRASAL_VERB_ID, "give in", status="pending", is_phrasal_verb=True,
        )
        _insert_candidate(
            conn, UNRELATED_REPLACEMENT_ID, "orphan", status="pending",
            has_custom_context_fragment=True,
        )
    return engine, cfg


def _breakdown_row(engine: Engine, candidate_id: int) -> tuple[object, ...] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT decision_method, cambridge, cefrpy, efllex_distribution, oxford, kelly"
                " FROM cefr_breakdowns WHERE candidate_id = :cid"
            ),
            {"cid": candidate_id},
        ).fetchone()
    return tuple(row) if row is not None else None


def test_replacement_gets_breakdown_and_usage_of_original(
    engine_before_migration: tuple[Engine, Config],
) -> None:
    engine, cfg = engine_before_migration

    command.upgrade(cfg, REVISION_UNDER_TEST)

    assert _breakdown_row(engine, REPLACEMENT_ID) == _breakdown_row(engine, ORIGINAL_ID)
    assert _breakdown_row(engine, REPLACEMENT_ID) is not None
    with engine.connect() as conn:
        usage = conn.execute(
            text("SELECT usage_distribution FROM candidates WHERE id = :id"),
            {"id": REPLACEMENT_ID},
        ).scalar_one()
    assert usage == USAGE_JSON


def test_candidates_without_a_source_breakdown_are_left_alone(
    engine_before_migration: tuple[Engine, Config],
) -> None:
    engine, cfg = engine_before_migration

    command.upgrade(cfg, REVISION_UNDER_TEST)

    assert _breakdown_row(engine, PHRASAL_VERB_ID) is None
    assert _breakdown_row(engine, UNRELATED_REPLACEMENT_ID) is None


def test_migration_is_idempotent(
    engine_before_migration: tuple[Engine, Config],
) -> None:
    engine, cfg = engine_before_migration

    command.upgrade(cfg, REVISION_UNDER_TEST)
    command.downgrade(cfg, REVISION_BEFORE)
    command.upgrade(cfg, REVISION_UNDER_TEST)

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM cefr_breakdowns")).scalar_one()
    assert count == 2
