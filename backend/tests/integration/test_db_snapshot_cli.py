"""The database copy `make update` takes before checkout and puts back on rollback."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from backend.cli import db_snapshot
from backend.infrastructure.persistence.database_backup import BACKUPS_KEPT, DatabaseBackup

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
    assert capsys.readouterr().out.strip() == db_snapshot.NO_DATABASE
    assert not db_path.exists()
    _write(db_path, "created by the new version")

    assert db_snapshot.main(["restore", "--none"]) == 0

    assert not db_path.exists()
    aside = list((db_path.parent / "backups").glob("failed-update-*.db"))
    assert len(aside) == 1
    assert _read(aside[0]) == ["created by the new version"]


@pytest.mark.parametrize("copy", ["", "nowhere.db", "NO_DATABASE"])
def test_restore_without_a_real_copy_refuses(
    db_path: Path, tmp_path: Path, copy: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(db_path, "current")

    assert db_snapshot.main(["restore", copy]) != 0

    assert _read(db_path) == ["current"]


def test_restore_of_a_file_that_is_not_a_database_fails(db_path: Path, tmp_path: Path) -> None:
    _write(db_path, "current")
    garbage = tmp_path / "garbage.db"
    garbage.write_text("not a database")

    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        db_snapshot.main(["restore", str(garbage)])

    assert _read(db_path) == ["current"]


def test_migration_backups_never_retire_the_update_copy(
    db_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _write(db_path, "old")
    db_snapshot.main(["take"])
    snapshot = capsys.readouterr().out.strip()

    for _ in range(BACKUPS_KEPT + 2):
        DatabaseBackup(db_path).take()

    assert Path(snapshot).name.startswith("update-")
    assert Path(snapshot).is_file()
