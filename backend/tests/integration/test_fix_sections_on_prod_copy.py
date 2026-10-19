"""`make fix-sections` on a copy of the real database.

Runs only on request, because it reads the prod copy's database (read-only, through an
sqlite backup into a temporary directory; the script runs on the copy):

    FIX_SECTIONS_PROD_COPY=1 DICTIONARIES_DIR=... .venv/bin/python -m pytest \\
        backend/tests/integration/test_fix_sections_on_prod_copy.py -q -s

`FIX_SECTIONS_PROD_DB` points at another database file if needed. The database must be at
revision 0049. The progress of each source before and after is printed for the commit that
ran this test.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from scripts.fix_sections import fix_sections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("FIX_SECTIONS_PROD_COPY") != "1",
        reason="reads the prod database; set FIX_SECTIONS_PROD_COPY=1 to run",
    ),
]

DEFAULT_PROD_DB = Path.home() / "projects" / "anything-to-anki-prod" / "data" / "app.db"
REVISION_BEFORE = "0049"
NO_CHOICE = "none"
GENERATION_TABLES = (
    "candidate_meanings", "candidate_media", "candidate_tts", "candidate_clozes",
)

Row = tuple[object, ...]


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


def _generation(conn: sqlite3.Connection) -> dict[str, dict[object, Row]]:
    """Every generated result, by the phrase it was made for."""
    return {
        table: {
            row[0]: tuple(row)
            for row in conn.execute(f"SELECT phrase_id, * FROM {table}")  # noqa: S608
        }
        for table in GENERATION_TABLES
    }


def _choices(conn: sqlite3.Connection) -> dict[int, str]:
    return dict(conn.execute("SELECT id, choice FROM phrases"))


def _word_decisions(conn: sqlite3.Connection) -> dict[int, str]:
    return dict(conn.execute("SELECT id, status FROM candidates WHERE status != 'pending'"))


def _progress(conn: sqlite3.Connection) -> dict[int, tuple[int, int, int, int]]:
    """Per source: phrases, shown phrases, decided phrases, shown phrases with a meaning."""
    rows = conn.execute(
        "SELECT c.source_id, count(*),"
        " sum(p.shown_by IS NOT NULL),"
        " sum(p.choice != 'none'),"
        " sum(p.shown_by IS NOT NULL AND EXISTS"
        "   (SELECT 1 FROM candidate_meanings m WHERE m.phrase_id = p.id))"
        " FROM phrases p JOIN candidates c ON c.id = p.candidate_id GROUP BY c.source_id"
    )
    return {row[0]: (row[1], row[2], row[3], row[4]) for row in rows}


def _sections(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    result: dict[int, dict[str, int]] = {}
    for source_id, section, count in conn.execute(
        "SELECT c.source_id, p.earned_section, count(*) FROM phrases p"
        " JOIN candidates c ON c.id = p.candidate_id GROUP BY 1, 2"
    ):
        result.setdefault(source_id, {})[str(section)] = count
    return result


def test_fix_sections_on_the_prod_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _copy(Path(os.environ.get("FIX_SECTIONS_PROD_DB", str(DEFAULT_PROD_DB))), db_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            REVISION_BEFORE
        )
        choices_before = _choices(conn)
        words_before = _word_decisions(conn)
        generation_before = _generation(conn)
        progress_before = _progress(conn)

    report = fix_sections(f"sqlite:///{db_path}")

    with sqlite3.connect(db_path) as conn:
        unsectioned = conn.execute(
            "SELECT count(*) FROM phrases WHERE earned_section IS NULL",
        ).fetchone()[0]
        choices_after = _choices(conn)
        words_after = _word_decisions(conn)
        generation_after = _generation(conn)
        progress_after = _progress(conn)
        sections = _sections(conn)

    # The numbers go into the commit that ran this test.
    print(  # noqa: T201
        f"phrases stamped: {report.phrases_stamped}, sources rebuilt: {report.sources_rebuilt},"
        f" failed: {report.failed}, phrases before: {len(choices_before)},"
        f" after: {len(choices_after)}",
    )
    print("per source (phrases, shown, decided, shown with meaning):")  # noqa: T201
    for source_id in sorted(set(progress_before) | set(progress_after)):
        print(  # noqa: T201
            f"  source {source_id}: before {progress_before.get(source_id)}"
            f" after {progress_after.get(source_id)} sections {sections.get(source_id)}",
        )

    assert unsectioned == 0
    assert report.failed == []
    decided = {pid for pid, choice in choices_before.items() if choice != NO_CHOICE}
    assert {pid: choices_after.get(pid) for pid in decided} == {
        pid: choices_before[pid] for pid in decided
    }
    assert words_after == words_before
    for table, before in generation_before.items():
        kept = {pid: generation_after[table].get(pid) for pid in before}
        assert kept == before, table
