"""Re-point media paths in the DB at this working copy's media folder.

Media paths are stored absolute, e.g.
/Users/you/project/data/media/42/123_screenshot.webp. After the working copy
is moved (or for rows written back when the app ran in Docker, as
/data/media/42/...), they no longer match the files on disk.

Every path keeps its ``<source_id>/<file>`` tail and gets the current media
root as prefix.

Usage:
    python scripts/relocate_media_paths.py          # dry-run
    python scripts/relocate_media_paths.py --apply  # apply
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PATH_SEPARATOR = "/"
# "<source_id>/<file name>" — the part of a media path that survives a move.
TAIL_COMPONENTS = 2

TABLES_COLUMNS: list[tuple[str, list[str]]] = [
    ("candidate_media", ["screenshot_path", "audio_path"]),
    ("candidate_pronunciations", ["us_audio_path", "uk_audio_path"]),
    ("candidate_tts", ["audio_path"]),
]


def get_media_root() -> str:
    return os.path.abspath(
        os.environ.get(
            "MEDIA_ROOT",
            os.path.join(os.getenv("DATA_DIR", "./data"), "media"),
        )
    )


def relocated_path(stored: str, media_root: str) -> str:
    tail = stored.split(PATH_SEPARATOR)[-TAIL_COMPONENTS:]
    return PATH_SEPARATOR.join([media_root.rstrip(PATH_SEPARATOR), *tail])


def relocate(db_path: str, media_root: str, *, apply: bool) -> int:
    """Return the number of outdated paths; rewrite them when ``apply`` is set."""
    conn = sqlite3.connect(db_path)
    total = 0

    for table, columns in TABLES_COLUMNS:
        for col in columns:
            rows = conn.execute(
                f"SELECT candidate_id, {col} FROM {table} WHERE {col} IS NOT NULL"  # noqa: S608
            ).fetchall()
            outdated = [
                (relocated_path(stored, media_root), candidate_id)
                for candidate_id, stored in rows
                if relocated_path(stored, media_root) != stored
            ]
            if not outdated:
                continue
            print(f"  {table}.{col}: {len(outdated)} rows")
            total += len(outdated)
            if apply:
                conn.executemany(
                    f"UPDATE {table} SET {col} = ? WHERE candidate_id = ?",  # noqa: S608
                    outdated,
                )

    if apply:
        conn.commit()
    conn.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-point media paths at this working copy.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--db", default=None, help="Path to app.db (default: DATA_DIR/app.db)")
    args = parser.parse_args()

    db_path = args.db or os.path.join(os.getenv("DATA_DIR", "./data"), "app.db")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    media_root = get_media_root()
    print(f"DB: {db_path}")
    print(f"Media root: {media_root}\n")

    total = relocate(db_path, media_root, apply=args.apply)

    if total == 0:
        print("Nothing to relocate.")
    elif args.apply:
        print(f"\nUpdated {total} paths.")
    else:
        print(f"\nTotal: {total} paths to update.")
        print("Dry-run mode. Run with --apply to update.")


if __name__ == "__main__":
    main()
