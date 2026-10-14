"""Migration 0049 on a copy of the real database: nothing is lost.

Runs only on request, because it reads the prod copy's database (read-only; the
migration runs on a copy in a temporary directory):

    MIGRATION_PROD_COPY=1 DICTIONARIES_DIR=... .venv/bin/python -m pytest \\
        backend/tests/integration/test_migration_0049_on_prod_copy.py -q -s

`MIGRATION_PROD_DB` points at another database file if needed. The database must be
at revision 0048.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("MIGRATION_PROD_COPY") != "1",
        reason="reads the prod database; set MIGRATION_PROD_COPY=1 to run",
    ),
]

DEFAULT_PROD_DB = Path.home() / "projects" / "anything-to-anki-prod" / "data" / "app.db"
REVISION_BEFORE = "0048"
REVISION_UNDER_TEST = "0049"
RESULT_TABLES = ("candidate_meanings", "candidate_media", "candidate_tts", "candidate_clozes")
PHRASE_LEVEL_JOB_TYPES = ("polish", "meaning", "media", "tts")


def _copy(source: Path, target: Path) -> None:
    original = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(target)
        try:
            original.backup(copy)
        finally:
            copy.close()
    finally:
        original.close()


def _count(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def _upgrade(db_path: Path) -> None:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, REVISION_UNDER_TEST)


def test_prod_copy_keeps_every_card_result_job_and_export(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _copy(Path(os.environ.get("MIGRATION_PROD_DB", str(DEFAULT_PROD_DB))), db_path)
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
        REVISION_BEFORE
    )
    cards = _count(conn, "SELECT count(*) FROM candidates")
    words = _count(
        conn,
        "SELECT count(*) FROM (SELECT DISTINCT source_id, lower(lemma), is_phrasal_verb"
        " FROM candidates)",
    )
    results = {t: _count(conn, f"SELECT count(*) FROM {t}") for t in RESULT_TABLES}  # noqa: S608
    synced = _count(conn, "SELECT count(*) FROM anki_synced_cards")
    notes = _count(conn, "SELECT count(DISTINCT anki_note_id) FROM anki_synced_cards")
    phrase_jobs = _count(
        conn,
        f"SELECT count(*) FROM jobs WHERE candidate_id IS NOT NULL"  # noqa: S608
        f" AND job_type IN {PHRASE_LEVEL_JOB_TYPES}",
    )
    jobs = _count(conn, "SELECT count(*) FROM jobs")
    reports = _count(
        conn,
        "SELECT count(*) FROM card_reports WHERE candidate_id IN (SELECT id FROM candidates)",
    )
    conn.close()

    _upgrade(db_path)

    conn = sqlite3.connect(db_path)
    print(  # noqa: T201 — the numbers go into the commit that ran this test
        f"cards={cards} words={words} results={results} synced={synced} notes={notes}"
        f" jobs={jobs} phrase_jobs={phrase_jobs} reports={reports}"
    )
    assert _count(conn, "SELECT count(*) FROM phrases") == cards
    assert _count(conn, "SELECT count(*) FROM candidates") == words
    for table, before in results.items():
        assert _count(conn, f"SELECT count(*) FROM {table}") == before, table  # noqa: S608
    assert _count(conn, "SELECT count(*) FROM anki_synced_cards") == synced
    assert _count(conn, "SELECT count(*) FROM anki_synced_cards WHERE phrase_id IS NULL") == 0
    assert _count(conn, "SELECT count(*) FROM anki_notes") == notes
    assert _count(conn, "SELECT count(*) FROM jobs") == jobs
    assert _count(conn, "SELECT count(*) FROM jobs WHERE phrase_id IS NOT NULL") == phrase_jobs
    assert _count(conn, "SELECT count(*) FROM card_reports WHERE phrase_id IS NOT NULL") == (
        reports
    )
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()
