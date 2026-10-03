"""Migration 0036 moves quick-reason comments of old reports into reasons."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0035"
REVISION_UNDER_TEST = "0036"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_quick_reason_comments_become_reasons(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_BEFORE)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        for report_id, comment in ((1, "Wrong word form"), (2, "the phrase is cut")):
            conn.execute(
                text(
                    "INSERT INTO card_reports (id, source_id, source_title, candidate_id,"
                    " lemma, context_fragment, zipf_frequency, fragment_unknown_count,"
                    " is_phrasal_verb, comment, created_at)"
                    " VALUES (:id, 1, 's', 1, 'word', 'ctx', 3.0, 0, 0, :comment,"
                    " '2026-01-01 00:00:00')"
                ),
                {"id": report_id, "comment": comment},
            )

    command.upgrade(cfg, REVISION_UNDER_TEST)

    with engine.connect() as conn:
        query = text("SELECT id, reasons, comment FROM card_reports ORDER BY id")
        rows = conn.execute(query).all()
    assert [tuple(row) for row in rows] == [
        (1, '["Wrong word form"]', ""),
        (2, "[]", "the phrase is cut"),
    ]
