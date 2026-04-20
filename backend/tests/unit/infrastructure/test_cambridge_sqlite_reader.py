"""Tests for CambridgeSQLiteReader."""
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


def _build_db(tmp_path: Path) -> Path:
    """Create a test SQLite DB with sample data."""
    db_path = tmp_path / "test_cambridge.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)

    # Entry 1: "hello" — has both US and UK audio
    conn.execute(
        "INSERT INTO entries VALUES (1, 'hello', 'hello', ?, '[]', '[]', ?, ?)",
        (
            json.dumps(["exclamation", "noun"]),
            json.dumps(["https://uk.audio/hello.mp3"]),
            json.dumps(["https://us.audio/hello.mp3"]),
        ),
    )
    conn.execute(
        "INSERT INTO senses VALUES (1, 1, 'greeting', 'A1', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps(["informal"]),),
    )

    # Entry 2: "test" as noun — B1
    conn.execute(
        "INSERT INTO entries VALUES (2, 'test', 'test', ?, '[]', '[]', '[]', '[]')",
        (json.dumps(["noun"]),),
    )
    conn.execute(
        "INSERT INTO senses VALUES (2, 2, 'an exam', 'B1', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps([]),),
    )
    conn.execute(
        "INSERT INTO senses VALUES (3, 2, 'medical test', 'B2', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps(["formal"]),),
    )

    # Entry 3: "test" as verb — A2
    conn.execute(
        "INSERT INTO entries VALUES (3, 'test', 'test', ?, '[]', '[]', '[]', '[]')",
        (json.dumps(["verb"]),),
    )
    conn.execute(
        "INSERT INTO senses VALUES (4, 3, 'to examine', 'A2', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps([]),),
    )

    # Entry 4: "rare" — no audio, empty level on one sense
    conn.execute(
        "INSERT INTO entries VALUES (4, 'rare', 'rare', ?, '[]', '[]', '[]', '[]')",
        (json.dumps(["adjective"]),),
    )
    conn.execute(
        "INSERT INTO senses VALUES (5, 4, 'not common', 'B2', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps([]),),
    )
    conn.execute(
        "INSERT INTO senses VALUES (6, 4, 'lightly cooked', '', '[]', '[]', ?, '[]', '[]', '')",
        (json.dumps(["cooking"]),),
    )

    # Entry 5: "cool" — US audio only (first entry), second entry has UK
    conn.execute(
        "INSERT INTO entries VALUES (5, 'cool', 'cool', ?, '[]', '[]', '[]', ?)",
        (
            json.dumps(["adjective"]),
            json.dumps(["https://us.audio/cool.mp3"]),
        ),
    )
    conn.execute(
        "INSERT INTO entries VALUES (6, 'cool', 'cool', ?, '[]', '[]', ?, '[]')",
        (
            json.dumps(["verb"]),
            json.dumps(["https://uk.audio/cool.mp3"]),
        ),
    )
    conn.execute(
        "INSERT INTO senses VALUES (7, 5, 'not warm', 'A2', '[]', '[]', '[]', '[]', '[]', '')",
    )
    conn.execute(
        "INSERT INTO senses VALUES (8, 6, 'to make cold', 'B1', '[]', '[]', '[]', '[]', '[]', '')",
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def reader(tmp_path: Path) -> Generator[CambridgeSQLiteReader]:
    db_path = _build_db(tmp_path)
    r = CambridgeSQLiteReader(db_path)
    yield r
    r.close()


# --- Audio URL tests ---

class TestGetAudioUrls:
    def test_both(self, reader: CambridgeSQLiteReader) -> None:
        us, uk = reader.get_audio_urls("hello")
        assert us == "https://us.audio/hello.mp3"
        assert uk == "https://uk.audio/hello.mp3"

    def test_unknown_word(self, reader: CambridgeSQLiteReader) -> None:
        us, uk = reader.get_audio_urls("xyznonexistent")
        assert us is None
        assert uk is None

    def test_partial_us_only_first_entry(self, reader: CambridgeSQLiteReader) -> None:
        """'cool' has US audio on first entry, UK on second."""
        us, uk = reader.get_audio_urls("cool")
        assert us == "https://us.audio/cool.mp3"
        assert uk == "https://uk.audio/cool.mp3"

    def test_no_audio(self, reader: CambridgeSQLiteReader) -> None:
        us, uk = reader.get_audio_urls("rare")
        assert us is None
        assert uk is None

    def test_case_insensitive(self, reader: CambridgeSQLiteReader) -> None:
        us, uk = reader.get_audio_urls("Hello")
        assert us == "https://us.audio/hello.mp3"
        assert uk == "https://uk.audio/hello.mp3"


# --- CEFR level tests ---

class TestGetCefrLevels:
    def test_basic(self, reader: CambridgeSQLiteReader) -> None:
        levels = reader.get_cefr_levels("hello")
        assert levels == ["A1"]

    def test_filters_by_pos(self, reader: CambridgeSQLiteReader) -> None:
        # NN -> noun, should get B1 and B2 from noun entry
        levels = reader.get_cefr_levels("test", pos_tag="NN")
        assert sorted(levels) == ["B1", "B2"]

    def test_verb_pos(self, reader: CambridgeSQLiteReader) -> None:
        levels = reader.get_cefr_levels("test", pos_tag="VB")
        assert levels == ["A2"]

    def test_fallback_to_all(self, reader: CambridgeSQLiteReader) -> None:
        # PRP$ (pronoun) won't match noun/verb for "test", falls back to all
        levels = reader.get_cefr_levels("test", pos_tag="PRP$")
        assert sorted(levels) == ["A2", "B1", "B2"]

    def test_skips_empty(self, reader: CambridgeSQLiteReader) -> None:
        # "rare" has one sense with B2 and one with empty level
        levels = reader.get_cefr_levels("rare")
        assert levels == ["B2"]

    def test_unknown_word(self, reader: CambridgeSQLiteReader) -> None:
        levels = reader.get_cefr_levels("xyznonexistent")
        assert levels == []


# --- Usage labels tests ---

class TestGetUsageLabels:
    def test_basic(self, reader: CambridgeSQLiteReader) -> None:
        labels = reader.get_usage_labels("hello")
        assert labels == [["informal"]]

    def test_filters_by_pos(self, reader: CambridgeSQLiteReader) -> None:
        # noun entry for "test" has two senses
        labels = reader.get_usage_labels("test", pos_tag="NN")
        assert labels == [[], ["formal"]]

    def test_empty_senses(self, reader: CambridgeSQLiteReader) -> None:
        # verb entry for "test" has one sense with no usages
        labels = reader.get_usage_labels("test", pos_tag="VB")
        assert labels == [[]]

    def test_unknown_word(self, reader: CambridgeSQLiteReader) -> None:
        labels = reader.get_usage_labels("xyznonexistent")
        assert labels == []
