from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.database import open_query_only

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

BACKUPS_DIR_NAME = "backups"
RETIRED_DIR_NAME = ".trash"
BACKUPS_KEPT = 5
BACKUP_PREFIX = "app-"
BACKUP_SUFFIX = ".db"
BACKUP_TIME_FORMAT = "%Y%m%dT%H%M%S%fZ"
SET_ASIDE_PREFIX = "failed-update-"
SQLITE_SIDE_FILE_SUFFIXES = ("-wal", "-shm")


class DatabaseBackup:
    """Copies of the database taken before migrations change it.

    Copies live in `backups/` next to the database as `app-<UTC>.db`; only the newest
    `BACKUPS_KEPT` stay there, older ones are moved to `backups/.trash/`, which keeps its
    newest `BACKUPS_KEPT` as well: older copies there are deleted.
    """

    def __init__(self, db_path: Path, keep: int = BACKUPS_KEPT) -> None:
        self._db_path = db_path
        self._dir = db_path.parent / BACKUPS_DIR_NAME
        self._keep = keep

    def take(self) -> Path:
        """A consistent copy of the database, through SQLite's online backup."""
        self._dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime(BACKUP_TIME_FORMAT)
        target = self._dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
        # Waits for a writer as every connection of the app does, and writes nothing.
        source = open_query_only(str(self._db_path))
        try:
            copy = sqlite3.connect(target)
            try:
                source.backup(copy)
            finally:
                copy.close()
        finally:
            source.close()
        logger.info("Database backed up to %s", target)
        self._retire_old()
        return target

    def restore(self, copy: Path) -> None:
        """Puts a copy taken by `take` back in place of the database, through the same
        online backup. Nothing else may use the database meanwhile."""
        if not copy.is_file():
            raise FileNotFoundError(copy)
        source = open_query_only(str(copy))
        try:
            target = sqlite3.connect(self._db_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        logger.info("Database restored from %s", copy)

    def set_aside(self) -> Path | None:
        """Moves the database out of the way, for a copy that had none before: the next
        start creates a fresh one. Kept in `backups/` under a name retention never counts."""
        if not self._db_path.exists():
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime(BACKUP_TIME_FORMAT)
        target = self._dir / f"{SET_ASIDE_PREFIX}{stamp}{BACKUP_SUFFIX}"
        for suffix in SQLITE_SIDE_FILE_SUFFIXES:
            side = self._db_path.with_name(self._db_path.name + suffix)
            if side.exists():
                side.rename(target.with_name(target.name + suffix))
        self._db_path.rename(target)
        logger.info("Database set aside to %s", target)
        return target

    def _retire_old(self) -> None:
        backups = _copies(self._dir)
        old = backups[: max(len(backups) - self._keep, 0)]
        retired = self._dir / RETIRED_DIR_NAME
        retired.mkdir(exist_ok=True)
        for backup in old:
            backup.rename(retired / backup.name)
            logger.info("Old database backup moved to %s", retired / backup.name)
        self._delete_oldest_retired(retired)

    def _delete_oldest_retired(self, retired: Path) -> None:
        copies = _copies(retired)
        for copy in copies[: max(len(copies) - self._keep, 0)]:
            copy.unlink()
            logger.info("Oldest database backup deleted: %s", copy)


def _copies(folder: Path) -> list[Path]:
    """The copies this class took in the folder, oldest first; any other file is left out."""
    taken: list[tuple[datetime, Path]] = []
    for path in folder.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        stamp = path.name.removeprefix(BACKUP_PREFIX).removesuffix(BACKUP_SUFFIX)
        try:
            taken.append((datetime.strptime(stamp, BACKUP_TIME_FORMAT), path))  # noqa: DTZ007 — compared with each other only
        except ValueError:
            continue
    return [path for _, path in sorted(taken)]
