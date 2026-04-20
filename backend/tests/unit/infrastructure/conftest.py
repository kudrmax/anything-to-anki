"""Shared fixtures for infrastructure unit tests."""
from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

_SCHEMA = """
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
    entry_id INTEGER NOT NULL,
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


def create_cambridge_test_db(tmp_path: Path, entries_data: list[dict[str, object]]) -> Path:
    """Create a test Cambridge SQLite DB with given entries and their senses.

    Each item in entries_data should have:
      - word: str
      - headword: str (optional, defaults to word)
      - pos: list[str] (optional, defaults to ["noun"])
      - uk_ipa, us_ipa, uk_audio, us_audio: list[str] (optional, default [])
      - senses: list[dict] with keys: definition, level, examples,
        labels_and_codes, usages, domains, regions, image_link (all optional)
    """
    db_path = tmp_path / "test_cambridge.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)

    entry_id = 0
    for entry in entries_data:
        entry_id += 1
        word = str(entry["word"])
        conn.execute(
            "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)",
            (
                entry_id,
                word,
                str(entry.get("headword", word)),
                json.dumps(entry.get("pos", ["noun"])),
                json.dumps(entry.get("uk_ipa", [])),
                json.dumps(entry.get("us_ipa", [])),
                json.dumps(entry.get("uk_audio", [])),
                json.dumps(entry.get("us_audio", [])),
            ),
        )
        senses = entry.get("senses", [])
        if isinstance(senses, list):
            for sense in senses:
                if isinstance(sense, dict):
                    conn.execute(
                        "INSERT INTO senses (entry_id, definition, level, examples,"
                        " labels_and_codes, usages, domains, regions, image_link)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            entry_id,
                            sense.get("definition", ""),
                            sense.get("level", ""),
                            json.dumps(sense.get("examples", [])),
                            json.dumps(sense.get("labels_and_codes", [])),
                            json.dumps(sense.get("usages", [])),
                            json.dumps(sense.get("domains", [])),
                            json.dumps(sense.get("regions", [])),
                            sense.get("image_link", ""),
                        ),
                    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def cambridge_reader(tmp_path: Path) -> Generator[CambridgeSQLiteReader]:
    """Create a CambridgeSQLiteReader with an empty test DB."""
    db_path = create_cambridge_test_db(tmp_path, [])
    reader = CambridgeSQLiteReader(db_path)
    yield reader
    reader.close()
