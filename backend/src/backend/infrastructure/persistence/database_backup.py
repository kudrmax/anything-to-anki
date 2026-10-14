from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

BACKUPS_DIR_NAME = "backups"
RETIRED_DIR_NAME = ".trash"
BACKUPS_KEPT = 5
BACKUP_PREFIX = "app-"
BACKUP_SUFFIX = ".db"
BACKUP_TIME_FORMAT = "%Y%m%dT%H%M%S%fZ"


class DatabaseBackup:
    """Copies of the database taken before migrations change it.

    Copies live in `backups/` next to the database as `app-<UTC>.db`; only the newest
    `BACKUPS_KEPT` stay there, older ones are moved to `backups/.trash/`, never deleted.
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
        source = sqlite3.connect(self._db_path)
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

    def _retire_old(self) -> None:
        backups = sorted(self._dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"))
        old = backups[: max(len(backups) - self._keep, 0)]
        if not old:
            return
        retired = self._dir / RETIRED_DIR_NAME
        retired.mkdir(exist_ok=True)
        for backup in old:
            backup.rename(retired / backup.name)
            logger.info("Old database backup moved to %s", retired / backup.name)
