"""Media paths in the DB are absolute; the script re-points them after a move."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from scripts.relocate_media_paths import relocate, relocated_path

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

MEDIA_ROOT = "/new/place/data/media"


@pytest.mark.parametrize(
    "stored",
    [
        "/data/media/7/4807_screenshot.webp",
        "/Users/me/Applications/app/data/media/7/4807_screenshot.webp",
    ],
    ids=["docker-era", "previous-folder"],
)
def test_path_is_moved_under_current_media_root(stored: str) -> None:
    assert relocated_path(stored, MEDIA_ROOT) == f"{MEDIA_ROOT}/7/4807_screenshot.webp"


def test_path_already_under_media_root_is_unchanged() -> None:
    current = f"{MEDIA_ROOT}/7/4807_screenshot.webp"

    assert relocated_path(current, MEDIA_ROOT) == current


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE candidate_media (candidate_id INTEGER PRIMARY KEY,"
        " screenshot_path TEXT, audio_path TEXT)"
    )
    conn.execute(
        "CREATE TABLE candidate_pronunciations (candidate_id INTEGER PRIMARY KEY,"
        " us_audio_path TEXT, uk_audio_path TEXT)"
    )
    conn.execute("CREATE TABLE candidate_tts (candidate_id INTEGER PRIMARY KEY, audio_path TEXT)")
    conn.execute(
        "INSERT INTO candidate_media VALUES (1, '/old/data/media/3/1_screenshot.webp', NULL)"
    )
    conn.execute(
        "INSERT INTO candidate_pronunciations VALUES"
        " (1, '/old/data/media/3/1_pron_us.mp3', ?)",
        (f"{MEDIA_ROOT}/3/1_pron_uk.mp3",),
    )
    conn.execute("INSERT INTO candidate_tts VALUES (1, '/data/media/3/1_tts.m4a')")
    conn.commit()
    conn.close()


def _all_paths(path: Path) -> list[str | None]:
    conn = sqlite3.connect(path)
    rows = [
        *conn.execute("SELECT screenshot_path, audio_path FROM candidate_media").fetchone(),
        *conn.execute(
            "SELECT us_audio_path, uk_audio_path FROM candidate_pronunciations"
        ).fetchone(),
        *conn.execute("SELECT audio_path FROM candidate_tts").fetchone(),
    ]
    conn.close()
    return rows


def test_dry_run_reports_but_changes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    _make_db(db)
    before = _all_paths(db)

    outdated = relocate(str(db), MEDIA_ROOT, apply=False)

    assert outdated == 3
    assert _all_paths(db) == before


def test_apply_rewrites_every_outdated_path(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    _make_db(db)

    relocate(str(db), MEDIA_ROOT, apply=True)

    assert _all_paths(db) == [
        f"{MEDIA_ROOT}/3/1_screenshot.webp",
        None,
        f"{MEDIA_ROOT}/3/1_pron_us.mp3",
        f"{MEDIA_ROOT}/3/1_pron_uk.mp3",
        f"{MEDIA_ROOT}/3/1_tts.m4a",
    ]
    assert relocate(str(db), MEDIA_ROOT, apply=False) == 0
