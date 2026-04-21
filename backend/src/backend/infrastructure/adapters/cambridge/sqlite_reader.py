"""SQLite-based reader for Cambridge dictionary data.

Replaces the JSONL parser that loaded entire dictionary into RAM.
Each method does a targeted SELECT — nothing is cached in memory.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Penn Treebank POS tag → Cambridge POS string (shared with cefr_source)
_POS_TO_CAMBRIDGE: dict[str, str] = {
    "NN": "noun", "NNS": "noun", "NNP": "noun", "NNPS": "noun",
    "VB": "verb", "VBD": "verb", "VBG": "verb", "VBN": "verb",
    "VBP": "verb", "VBZ": "verb",
    "JJ": "adjective", "JJR": "adjective", "JJS": "adjective",
    "RB": "adverb", "RBR": "adverb", "RBS": "adverb",
    "UH": "exclamation", "MD": "modal verb",
    "IN": "preposition", "DT": "determiner",
    "PRP": "pronoun", "PRP$": "pronoun", "CC": "conjunction",
}


class CambridgeSQLiteReader:
    """Read-only access to Cambridge dictionary SQLite database.

    Infrastructure-layer component shared by CambridgeCEFRSource,
    CambridgeUsageLookup, and CambridgePronunciationSource.
    Domain layer knows nothing about this class.
    """

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            logger.warning("Cambridge SQLite DB not found: %s", db_path)
        self._db_path = db_path
        # Open connection in read-only mode. check_same_thread=False
        # because container creates reader once, shared across requests.
        self._conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        """Return (us_url, uk_url) for the given lemma."""
        cursor = self._conn.execute(
            "SELECT us_audio, uk_audio FROM entries WHERE word = ?",
            (lemma.lower(),),
        )
        us_url: str | None = None
        uk_url: str | None = None
        for row in cursor:
            if us_url is None:
                us_list: list[str] = json.loads(row["us_audio"])
                if us_list:
                    us_url = us_list[0]
            if uk_url is None:
                uk_list: list[str] = json.loads(row["uk_audio"])
                if uk_list:
                    uk_url = uk_list[0]
            if us_url is not None and uk_url is not None:
                break
        return us_url, uk_url

    def get_cefr_levels(self, lemma: str, pos_tag: str | None = None) -> list[str]:
        """Return list of CEFR level strings for all matching senses.

        pos_tag: Penn Treebank tag (e.g. "NN", "VB"). If provided, filters
        entries by Cambridge POS. If no match, falls back to all entries.
        """
        cambridge_pos = _POS_TO_CAMBRIDGE.get(pos_tag, "") if pos_tag else ""

        # Try with POS filter first
        if cambridge_pos:
            levels = self._query_cefr_levels(lemma.lower(), cambridge_pos)
            if levels:
                return levels

        # Fallback: all entries for this word
        return self._query_cefr_levels(lemma.lower(), None)

    def _query_cefr_levels(self, word: str, cambridge_pos: str | None) -> list[str]:
        if cambridge_pos:
            cursor = self._conn.execute(
                """
                SELECT s.level FROM senses s
                JOIN entries e ON e.id = s.entry_id
                WHERE e.word = ? AND e.pos LIKE ?
                AND s.level != ''
                ORDER BY s.id
                """,
                (word, f'%"{cambridge_pos}"%'),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT s.level FROM senses s
                JOIN entries e ON e.id = s.entry_id
                WHERE e.word = ? AND s.level != ''
                ORDER BY s.id
                """,
                (word,),
            )
        return [row["level"] for row in cursor]

    def get_usage_labels(self, lemma: str, pos_tag: str | None = None) -> list[list[str]]:
        """Return usage labels for each sense of matching entries.

        Returns list of lists: one inner list per sense, containing raw usage strings.
        Senses with no usages return empty inner list.
        """
        cambridge_pos = _POS_TO_CAMBRIDGE.get(pos_tag, "") if pos_tag else ""

        if cambridge_pos:
            labels = self._query_usage_labels(lemma.lower(), cambridge_pos)
            if labels:
                return labels

        return self._query_usage_labels(lemma.lower(), None)

    def _query_usage_labels(self, word: str, cambridge_pos: str | None) -> list[list[str]]:
        if cambridge_pos:
            cursor = self._conn.execute(
                """
                SELECT s.usages FROM senses s
                JOIN entries e ON e.id = s.entry_id
                WHERE e.word = ? AND e.pos LIKE ?
                """,
                (word, f'%"{cambridge_pos}"%'),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT s.usages FROM senses s
                JOIN entries e ON e.id = s.entry_id
                WHERE e.word = ?
                """,
                (word,),
            )
        return [json.loads(row["usages"]) for row in cursor]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
