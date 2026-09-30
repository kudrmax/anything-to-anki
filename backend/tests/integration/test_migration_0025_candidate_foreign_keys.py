"""Migration 0025: enrichment follows its candidate, candidate ids are never reused.

Runs the real Alembic chain on a file-based SQLite DB: up to 0024, seed the
broken state (enrichment left behind by deleted candidates), then upgrade.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, event, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0024"
REVISION_UNDER_TEST = "0025"
SOURCE_ID = 1
LIVE_CANDIDATE_ID = 1
DELETED_CANDIDATE_ID = 7
FOREIGN_FILE_CANDIDATE_ID = 2
OTHER_SOURCE_ID = 99
ENRICHMENT_TABLES = (
    "candidate_meanings",
    "candidate_media",
    "candidate_pronunciations",
    "candidate_tts",
    "anki_synced_cards",
)


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _enrich(conn: Connection, candidate_id: int) -> None:
    file_prefix = f"/data/media/{SOURCE_ID}/{candidate_id}"
    params = {"cid": candidate_id, "prefix": file_prefix}
    conn.execute(
        text("INSERT INTO candidate_meanings (candidate_id, meaning) VALUES (:cid, 'm')"),
        params,
    )
    conn.execute(
        text(
            "INSERT INTO candidate_media (candidate_id, screenshot_path)"
            " VALUES (:cid, :prefix || '_screenshot.webp')"
        ),
        params,
    )
    conn.execute(
        text(
            "INSERT INTO candidate_pronunciations (candidate_id, us_audio_path)"
            " VALUES (:cid, :prefix || '_pron_us.mp3')"
        ),
        params,
    )
    conn.execute(
        text(
            "INSERT INTO candidate_tts (candidate_id, audio_path)"
            " VALUES (:cid, :prefix || '_tts.m4a')"
        ),
        params,
    )
    conn.execute(
        text("INSERT INTO anki_synced_cards (candidate_id, anki_note_id) VALUES (:cid, 1)"),
        params,
    )


def _insert_candidate(conn: Connection, lemma: str, candidate_id: int | None = None) -> int:
    result = conn.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
            " is_sweet_spot, context_fragment, fragment_purity, occurrences, status,"
            " is_phrasal_verb, has_custom_context_fragment)"
            " VALUES (:id, :source_id, :lemma, 'NOUN', 4.0, 1, 'ctx', 'clean', 1,"
            " 'pending', 0, 0)"
        ),
        {"id": candidate_id, "source_id": SOURCE_ID, "lemma": lemma},
    )
    new_id = result.lastrowid
    assert new_id is not None
    return new_id


def _count(conn: Connection, table: str, candidate_id: int) -> int:
    count: int = conn.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE candidate_id = :cid"),
        {"cid": candidate_id},
    ).scalar_one()
    return count


@pytest.fixture
def migrated(tmp_path: Path) -> Engine:
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
        _insert_candidate(conn, "advance", LIVE_CANDIDATE_ID)
        _enrich(conn, LIVE_CANDIDATE_ID)
        # The state a deleted candidate left behind: its enrichment, no candidate.
        _enrich(conn, DELETED_CANDIDATE_ID)
        # A candidate that inherited files generated for another source's word.
        _insert_candidate(conn, "pant", FOREIGN_FILE_CANDIDATE_ID)
        foreign = f"/data/media/{OTHER_SOURCE_ID}/{FOREIGN_FILE_CANDIDATE_ID}"
        conn.execute(
            text(
                "INSERT INTO candidate_media (candidate_id, screenshot_path, audio_path)"
                " VALUES (:cid, :shot, :audio)"
            ),
            {
                "cid": FOREIGN_FILE_CANDIDATE_ID,
                "shot": f"{foreign}_screenshot.webp",
                "audio": f"{foreign}_audio.m4a",
            },
        )
        conn.execute(
            text(
                "INSERT INTO candidate_pronunciations (candidate_id, us_audio_path)"
                " VALUES (:cid, :path)"
            ),
            {"cid": FOREIGN_FILE_CANDIDATE_ID, "path": f"{foreign}_pron_us.mp3"},
        )
        conn.execute(
            text("INSERT INTO candidate_tts (candidate_id, audio_path) VALUES (:cid, :path)"),
            {"cid": FOREIGN_FILE_CANDIDATE_ID, "path": f"{foreign}_tts.m4a"},
        )

    command.upgrade(cfg, REVISION_UNDER_TEST)
    engine.dispose()
    app_engine = create_engine(db_url)
    event.listen(app_engine, "connect", database._enable_sqlite_foreign_keys)
    return app_engine


def test_orphan_enrichment_is_removed_and_live_enrichment_kept(migrated: Engine) -> None:
    with migrated.connect() as conn:
        for table in ENRICHMENT_TABLES:
            assert _count(conn, table, DELETED_CANDIDATE_ID) == 0, table
            assert _count(conn, table, LIVE_CANDIDATE_ID) == 1, table


def test_new_candidate_never_takes_an_id_seen_before(migrated: Engine) -> None:
    with migrated.begin() as conn:
        new_id = _insert_candidate(conn, "instant")

    assert new_id > DELETED_CANDIDATE_ID


def test_deleting_a_candidate_cascades_to_its_enrichment(migrated: Engine) -> None:
    with migrated.begin() as conn:
        conn.execute(text("DELETE FROM candidates WHERE id = :id"), {"id": LIVE_CANDIDATE_ID})

    with migrated.connect() as conn:
        for table in (*ENRICHMENT_TABLES, "cefr_breakdowns"):
            assert _count(conn, table, LIVE_CANDIDATE_ID) == 0, table


def test_deleting_a_source_cascades_to_its_candidates(migrated: Engine) -> None:
    with migrated.begin() as conn:
        conn.execute(text("DELETE FROM sources WHERE id = :id"), {"id": SOURCE_ID})

    with migrated.connect() as conn:
        remaining = conn.execute(text("SELECT COUNT(*) FROM candidates")).scalar_one()
    assert remaining == 0


def test_enrichment_with_files_of_another_source_is_removed(migrated: Engine) -> None:
    with migrated.connect() as conn:
        for table in ("candidate_media", "candidate_pronunciations", "candidate_tts"):
            assert _count(conn, table, FOREIGN_FILE_CANDIDATE_ID) == 0, table
