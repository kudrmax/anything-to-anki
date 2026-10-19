"""The database is copied before migrations change it, and connections wait for locks."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.database import (
    SQLITE_BUSY_TIMEOUT_MS,
    create_session_factory,
    run_alembic_migrations,
)
from backend.infrastructure.persistence.database_backup import BACKUPS_KEPT, DatabaseBackup
from sqlalchemy import text

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

OLDER_REVISION = "0048"


def _upgrade(db_path: Path, revision: str) -> None:
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(database.__file__).rsplit("/infrastructure/", 1)[0] + "/alembic",
    )
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, revision)


def _backups(db_path: Path) -> list[Path]:
    return sorted((db_path.parent / "backups").glob("app-*.db"))


def test_pending_migrations_are_preceded_by_a_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _upgrade(db_path, OLDER_REVISION)

    run_alembic_migrations(f"sqlite:///{db_path}")

    backups = _backups(db_path)
    assert len(backups) == 1
    factory = create_session_factory(f"sqlite:///{backups[0]}")
    with factory() as session:
        version = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == OLDER_REVISION


def test_no_backup_when_nothing_is_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    run_alembic_migrations(f"sqlite:///{db_path}")
    run_alembic_migrations(f"sqlite:///{db_path}")

    assert _backups(db_path) == []


def test_only_the_newest_backups_stay_the_rest_are_moved_aside(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _upgrade(db_path, OLDER_REVISION)
    backup = DatabaseBackup(db_path)

    taken = [backup.take() for _ in range(BACKUPS_KEPT + 2)]

    assert _backups(db_path) == taken[2:]
    retired = sorted((db_path.parent / "backups" / ".trash").iterdir())
    assert [p.name for p in retired] == [p.name for p in taken[:2]]


def test_the_moved_aside_backups_keep_only_the_newest_too(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _upgrade(db_path, OLDER_REVISION)
    backup = DatabaseBackup(db_path)

    taken = [backup.take() for _ in range(2 * BACKUPS_KEPT + 2)]

    assert _backups(db_path) == taken[-BACKUPS_KEPT:]
    retired = sorted((db_path.parent / "backups" / ".trash").iterdir())
    assert [p.name for p in retired] == [p.name for p in taken[2:BACKUPS_KEPT + 2]]


def test_a_file_not_named_as_a_backup_is_never_moved_counted_or_deleted(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _upgrade(db_path, OLDER_REVISION)
    backups = db_path.parent / "backups"
    (backups / ".trash").mkdir(parents=True)
    foreign = [backups / "app-before-upgrade.db", backups / ".trash" / "app-keep-me.db"]
    for path in foreign:
        path.write_bytes(b"mine")
    backup = DatabaseBackup(db_path)

    taken = [backup.take() for _ in range(2 * BACKUPS_KEPT + 1)]

    assert all(path.read_bytes() == b"mine" for path in foreign)
    assert sorted(p for p in backups.glob("app-*.db") if p not in foreign) == (
        taken[-BACKUPS_KEPT:]
    )
    retired = sorted(p.name for p in (backups / ".trash").iterdir() if p not in foreign)
    assert retired == [p.name for p in taken[1:BACKUPS_KEPT + 1]]


def test_connections_wait_for_a_locked_database(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    with factory() as session:
        timeout = session.execute(text("PRAGMA busy_timeout")).scalar()
    assert timeout == SQLITE_BUSY_TIMEOUT_MS
