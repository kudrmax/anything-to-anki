#!/usr/bin/env python3
"""Convert Cambridge JSONL dictionary to SQLite database."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

SCHEMA = """
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    headword TEXT NOT NULL,
    pos TEXT NOT NULL,
    uk_ipa TEXT NOT NULL,
    us_ipa TEXT NOT NULL,
    uk_audio TEXT NOT NULL,
    us_audio TEXT NOT NULL
);

CREATE TABLE senses (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    definition TEXT NOT NULL,
    level TEXT NOT NULL,
    examples TEXT NOT NULL,
    labels_and_codes TEXT NOT NULL,
    usages TEXT NOT NULL,
    domains TEXT NOT NULL,
    regions TEXT NOT NULL,
    image_link TEXT NOT NULL
);

CREATE INDEX idx_entries_word ON entries(word);
CREATE INDEX idx_senses_entry_id ON senses(entry_id);
"""

BATCH_SIZE = 5000


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes."""
    conn.executescript(SCHEMA)


def convert(input_path: Path, output_path: Path) -> None:
    """Read JSONL and write SQLite database."""
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    try:
        create_schema(conn)

        word_count = 0
        entry_count = 0
        sense_count = 0

        entry_rows: list[tuple[str, str, str, str, str, str, str]] = []
        sense_rows: list[tuple[int, str, str, str, str, str, str, str, str]] = []
        next_entry_id = 1

        with open(input_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Warning: skipping line {line_num}: {e}", file=sys.stderr)
                    continue

                word = data["word"].lower()
                word_count += 1

                for entry in data.get("entries", []):
                    entry_id = next_entry_id
                    next_entry_id += 1

                    entry_rows.append((
                        word,
                        entry.get("headword", word),
                        json.dumps(entry.get("pos", []), ensure_ascii=False),
                        json.dumps(entry.get("uk_ipa", []), ensure_ascii=False),
                        json.dumps(entry.get("us_ipa", []), ensure_ascii=False),
                        json.dumps(entry.get("uk_audio", []), ensure_ascii=False),
                        json.dumps(entry.get("us_audio", []), ensure_ascii=False),
                    ))
                    entry_count += 1

                    for sense in entry.get("senses", []):
                        sense_rows.append((
                            entry_id,
                            sense.get("definition", ""),
                            sense.get("level", ""),
                            json.dumps(sense.get("examples", []), ensure_ascii=False),
                            json.dumps(sense.get("labels_and_codes", []), ensure_ascii=False),
                            json.dumps(sense.get("usages", []), ensure_ascii=False),
                            json.dumps(sense.get("domains", []), ensure_ascii=False),
                            json.dumps(sense.get("regions", []), ensure_ascii=False),
                            sense.get("image_link", ""),
                        ))
                        sense_count += 1

                if len(entry_rows) >= BATCH_SIZE:
                    _flush(conn, entry_rows, sense_rows)
                    entry_rows.clear()
                    sense_rows.clear()

        # Flush remaining rows
        if entry_rows:
            _flush(conn, entry_rows, sense_rows)

        conn.commit()

        print(f"Words:   {word_count:,}")
        print(f"Entries: {entry_count:,}")
        print(f"Senses:  {sense_count:,}")
        print(f"Output:  {output_path}")

    finally:
        conn.close()


def _flush(
    conn: sqlite3.Connection,
    entry_rows: list[tuple[str, str, str, str, str, str, str]],
    sense_rows: list[tuple[int, str, str, str, str, str, str, str, str]],
) -> None:
    """Insert batched rows into the database."""
    conn.executemany(
        "INSERT INTO entries (word, headword, pos, uk_ipa, us_ipa, uk_audio, us_audio) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        entry_rows,
    )
    conn.executemany(
        "INSERT INTO senses (entry_id, definition, level, examples, labels_and_codes, "
        "usages, domains, regions, image_link) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        sense_rows,
    )
    conn.commit()


def main() -> None:
    """Parse arguments and run conversion."""
    parser = argparse.ArgumentParser(
        description="Convert Cambridge JSONL dictionary to SQLite database."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("dictionaries/cambridge.jsonl"),
        help="Path to input JSONL file (default: dictionaries/cambridge.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dictionaries/cambridge.db"),
        help="Path to output SQLite file (default: dictionaries/cambridge.db)",
    )
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()
