"""Every connection the app's engine factory opens runs on the WAL journal: a reader is not
held up by a write transaction open on another connection, and sees the state before it
(spec §5)."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.persistence.database import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_CACHE_SIZE_KIB,
    create_app_engine,
    open_query_only,
)
from sqlalchemy import text

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

pytestmark = pytest.mark.integration

# The reader fails at once instead of waiting: a reader that waits is the failure.
NO_WAIT = 0
SYNCHRONOUS_NORMAL = 1


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = create_app_engine(f"sqlite:///{tmp_path / 'app.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)"))
        conn.execute(text("INSERT INTO notes (id, body) VALUES (1, 'before')"))
    return engine


def test_every_connection_runs_with_the_wal_journal(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
        assert conn.exec_driver_sql("PRAGMA synchronous").scalar_one() == SYNCHRONOUS_NORMAL
        assert conn.exec_driver_sql("PRAGMA cache_size").scalar_one() == SQLITE_CACHE_SIZE_KIB
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_a_reader_is_not_held_up_by_an_open_write(engine: Engine) -> None:
    """EXCLUSIVE keeps every reader out under a rollback journal; under WAL a reader goes on
    reading the last commit."""
    with engine.connect() as writer, engine.connect() as reader:
        writer.exec_driver_sql("BEGIN EXCLUSIVE")
        writer.exec_driver_sql("UPDATE notes SET body = 'after' WHERE id = 1")
        reader.exec_driver_sql(f"PRAGMA busy_timeout = {NO_WAIT}")

        assert reader.exec_driver_sql("SELECT body FROM notes").scalar_one() == "before"

        writer.exec_driver_sql("COMMIT")
        reader.rollback()
        assert reader.exec_driver_sql("SELECT body FROM notes").scalar_one() == "after"


def test_a_query_only_connection_reads_a_wal_database_no_one_holds(
    engine: Engine, tmp_path: Path,
) -> None:
    """SQLite cannot open a WAL database `mode=ro` while no connection holds its files: the
    check script and the bench copies read through `open_query_only` instead."""
    engine.dispose()
    connection = open_query_only(str(tmp_path / "app.db"))
    try:
        assert connection.execute("SELECT body FROM notes").fetchone() == ("before",)
        with pytest.raises(Exception, match="readonly"):
            connection.execute("UPDATE notes SET body = 'never'")
    finally:
        connection.close()


def test_a_query_only_connection_leaves_a_rollback_journal_database_as_it_is(
    tmp_path: Path,
) -> None:
    """The bench copies and the check script read databases still in the rollback journal:
    reading them writes nothing, the journal mode included."""
    path = tmp_path / "rollback.db"
    setup = sqlite3.connect(path)
    setup.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    setup.execute("INSERT INTO notes (id, body) VALUES (1, 'kept')")
    setup.commit()
    setup.close()
    before = path.read_bytes()

    connection = open_query_only(str(path))
    try:
        assert connection.execute("SELECT body FROM notes").fetchone() == ("kept",)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("PRAGMA busy_timeout").fetchone() == (SQLITE_BUSY_TIMEOUT_MS,)
    finally:
        connection.close()

    assert path.read_bytes() == before
