"""The database copy `make update` takes before switching versions, and its return when
the update fails.

Usage:
    python -m backend.cli.db_snapshot take            # the copy's path, or NO_DATABASE
    python -m backend.cli.db_snapshot restore <path>  # puts the copy back
    python -m backend.cli.db_snapshot restore --none  # there was no DB: sets the new one aside
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.infrastructure.persistence.database import default_db_path
from backend.infrastructure.persistence.database_backup import (
    UPDATE_SNAPSHOT_PREFIX,
    DatabaseBackup,
)

TAKE = "take"
RESTORE = "restore"
NO_DATABASE = "NO_DATABASE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="db_snapshot")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(TAKE)
    restore = commands.add_parser(RESTORE)
    source = restore.add_mutually_exclusive_group(required=True)
    source.add_argument("copy", nargs="?")
    source.add_argument("--none", action="store_true")
    args = parser.parse_args(argv)

    db_path = Path(default_db_path())
    backup = DatabaseBackup(db_path, prefix=UPDATE_SNAPSHOT_PREFIX)
    if args.command == TAKE:
        print(backup.take() if db_path.exists() else NO_DATABASE)
        return 0
    if args.none:
        backup.set_aside()
        return 0
    copy = Path(args.copy)
    if not args.copy or not copy.is_file():
        print(f"ERROR: database copy '{args.copy}' not found", file=sys.stderr)
        return 1
    backup.restore(copy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
