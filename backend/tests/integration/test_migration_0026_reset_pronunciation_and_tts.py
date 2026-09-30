"""Migration 0026 drops pronunciation and TTS that may belong to another word.

Before 0025 a candidate could inherit these rows through a reused id, and
an audio file cannot be checked against the word it is attached to. They are
cheap to regenerate, so all of them are dropped; meanings and media stay.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0025"
REVISION_UNDER_TEST = "0026"
SOURCE_ID = 1
CANDIDATE_ID = 1


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_pronunciation_and_tts_are_dropped_and_the_rest_is_kept(tmp_path: Path) -> None:
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
        conn.execute(
            text(
                "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
                " is_sweet_spot, context_fragment, fragment_purity, occurrences, status,"
                " is_phrasal_verb, has_custom_context_fragment)"
                " VALUES (:id, :source_id, 'advance', 'NOUN', 4.0, 1, 'ctx', 'clean', 1,"
                " 'learn', 0, 0)"
            ),
            {"id": CANDIDATE_ID, "source_id": SOURCE_ID},
        )
        params = {"cid": CANDIDATE_ID}
        conn.execute(
            text("INSERT INTO candidate_meanings (candidate_id, meaning) VALUES (:cid, 'm')"),
            params,
        )
        conn.execute(
            text("INSERT INTO candidate_media (candidate_id, screenshot_path) VALUES (:cid, 's')"),
            params,
        )
        conn.execute(
            text(
                "INSERT INTO candidate_pronunciations (candidate_id, us_audio_path)"
                " VALUES (:cid, 'p')"
            ),
            params,
        )
        conn.execute(
            text("INSERT INTO candidate_tts (candidate_id, audio_path) VALUES (:cid, 't')"),
            params,
        )

    command.upgrade(cfg, REVISION_UNDER_TEST)

    with engine.connect() as conn:
        counts = {
            table: conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in (
                "candidate_pronunciations",
                "candidate_tts",
                "candidate_meanings",
                "candidate_media",
                "candidates",
            )
        }
    assert counts == {
        "candidate_pronunciations": 0,
        "candidate_tts": 0,
        "candidate_meanings": 1,
        "candidate_media": 1,
        "candidates": 1,
    }
