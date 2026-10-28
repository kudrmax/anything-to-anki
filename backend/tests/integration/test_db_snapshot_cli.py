"""The database copy `make update` takes before checkout and puts back on rollback."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from backend.cli import db_snapshot

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _write(db_path: Path, value: str) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
        connection.execute("DELETE FROM t")
        connection.execute("INSERT INTO t VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _read(db_path: Path) -> list[str]:
    connection = sqlite3.connect(db_path)
    try:
        return [row[0] for row in connection.execute("SELECT v FROM t")]
    finally:
        connection.close()


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    return tmp_path / "data" / "app.db"


def test_restore_puts_the_taken_copy_back(
    db_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _write(db_path, "old")

    assert db_snapshot.main(["take"]) == 0
    snapshot = capsys.readouterr().out.strip()
    _write(db_path, "migrated")
    assert db_snapshot.main(["restore", snapshot]) == 0

    assert _read(db_path) == ["old"]


def test_no_database_takes_no_copy_and_restore_sets_the_new_one_aside(
    db_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert db_snapshot.main(["take"]) == 0
    assert capsys.readouterr().out.strip() == ""
    assert not db_path.exists()
    _write(db_path, "created by the new version")

    assert db_snapshot.main(["restore"]) == 0

    assert not db_path.exists()
    aside = list((db_path.parent / "backups").glob("failed-update-*.db"))
    assert len(aside) == 1
    assert _read(aside[0]) == ["created by the new version"]


def test_restore_of_a_missing_copy_fails(db_path: Path, tmp_path: Path) -> None:
    _write(db_path, "current")

    assert db_snapshot.main(["restore", str(tmp_path / "nowhere.db")]) != 0

    assert _read(db_path) == ["current"]
