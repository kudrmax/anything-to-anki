"""The database copy `make update` takes before switching versions, and its return when
the update fails.

Usage:
    python -m backend.cli.db_snapshot take            # the copy's path; nothing without a DB
    python -m backend.cli.db_snapshot restore <path>  # puts the copy back
    python -m backend.cli.db_snapshot restore         # there was no DB: sets the new one aside
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.infrastructure.persistence.database import default_db_path
from backend.infrastructure.persistence.database_backup import DatabaseBackup

TAKE = "take"
RESTORE = "restore"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="db_snapshot")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(TAKE)
    restore = commands.add_parser(RESTORE)
    restore.add_argument("copy", nargs="?", default="")
    args = parser.parse_args(argv)

    db_path = Path(default_db_path())
    backup = DatabaseBackup(db_path)
    if args.command == TAKE:
        if db_path.exists():
            print(backup.take())
        return 0
    if not args.copy:
        backup.set_aside()
        return 0
    try:
        backup.restore(Path(args.copy))
    except FileNotFoundError:
        print(f"ERROR: database copy {args.copy} not found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
