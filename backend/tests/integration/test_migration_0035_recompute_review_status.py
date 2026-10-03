"""Migration 0035 brings source review statuses in line with candidate decisions.

Decisions made before the backend derived the status left sources stuck in a
status that disagrees with their candidates.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0034"
REVISION_UNDER_TEST = "0035"

# source id -> (status before, candidate statuses, expected status after)
CASES: dict[int, tuple[str, list[str], str]] = {
    1: ("done", ["learn", "pending"], "partially_reviewed"),
    2: ("done", ["pending", "pending"], "done"),
    3: ("partially_reviewed", ["learn", "known"], "reviewed"),
    4: ("reviewed", ["skip", "pending"], "partially_reviewed"),
    5: ("processing", ["learn"], "processing"),
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_review_status_follows_candidate_decisions(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_BEFORE)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for source_id, (status, candidate_statuses, _) in CASES.items():
            conn.execute(
                text(
                    "INSERT INTO sources (id, raw_text, title, status, input_method,"
                    " content_type, created_at)"
                    " VALUES (:id, 'text', 'title', :status, 'text_pasted', 'text',"
                    " '2026-01-01 00:00:00')"
                ),
                {"id": source_id, "status": status},
            )
            for candidate_status in candidate_statuses:
                conn.execute(
                    text(
                        "INSERT INTO candidates (source_id, lemma, pos, zipf_frequency,"
                        " is_sweet_spot, context_fragment, fragment_purity, occurrences,"
                        " status, is_phrasal_verb, has_custom_context_fragment)"
                        " VALUES (:source_id, 'word', 'NOUN', 4.0, 0, 'ctx', 'clean', 1,"
                        " :status, 0, 0)"
                    ),
                    {"source_id": source_id, "status": candidate_status},
                )

    command.upgrade(cfg, REVISION_UNDER_TEST)

    with engine.connect() as conn:
        statuses = dict(conn.execute(text("SELECT id, status FROM sources")).all())
    assert statuses == {source_id: expected for source_id, (_, _, expected) in CASES.items()}
