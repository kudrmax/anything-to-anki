"""Migrate Docker-era absolute paths to native absolute paths.

Docker stored paths like /data/media/42/123_screenshot.webp.
Native execution uses the real absolute path, e.g.
/Users/you/project/data/media/42/123_screenshot.webp.

Usage:
    python scripts/migrate_docker_paths.py          # dry-run
    python scripts/migrate_docker_paths.py --apply  # apply
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

OLD_PREFIX = "/data/media/"

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


def migrate(db_path: str, *, apply: bool) -> None:
    media_root = get_media_root()
    new_prefix = media_root.rstrip("/") + "/"

    print(f"DB: {db_path}")
    print(f"Old prefix: {OLD_PREFIX}")
    print(f"New prefix: {new_prefix}")
    print()

    conn = sqlite3.connect(db_path)
    total = 0

    for table, columns in TABLES_COLUMNS:
        for col in columns:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ?",  # noqa: S608
                (OLD_PREFIX + "%",),
            )
            count = cursor.fetchone()[0]
            if count:
                print(f"  {table}.{col}: {count} rows")
                total += count

    if total == 0:
        print("Nothing to migrate.")
        conn.close()
        return

    print(f"\nTotal: {total} paths to update.")

    if not apply:
        print("Dry-run mode. Run with --apply to update.")
        conn.close()
        return

    for table, columns in TABLES_COLUMNS:
        for col in columns:
            conn.execute(
                f"UPDATE {table} SET {col} = ? || substr({col}, ?) WHERE {col} LIKE ?",  # noqa: S608
                (new_prefix, len(OLD_PREFIX) + 1, OLD_PREFIX + "%"),
            )

    conn.commit()
    conn.close()
    print(f"Updated {total} paths.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Docker paths to native.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--db", default=None, help="Path to app.db (default: DATA_DIR/app.db)")
    args = parser.parse_args()

    db_path = args.db or os.path.join(os.getenv("DATA_DIR", "./data"), "app.db")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    migrate(db_path, apply=args.apply)


if __name__ == "__main__":
    main()
