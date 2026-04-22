"""Read-only SQLite reader for the unified dictionary cache."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class DictCacheReader:
    """Singleton-style read-only reader for dict.db."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path.exists():
            self._conn = sqlite3.connect(
                f"file:{db_path}?mode=ro", uri=True, check_same_thread=False,
            )
        else:
            logger.warning("Dictionary cache not found at %s", db_path)

    def get_cefr_sources(self) -> list[dict[str, str]]:
        if self._conn is None:
            return []
        rows = self._conn.execute(
            "SELECT DISTINCT source_name, priority FROM cefr"
        ).fetchall()
        return [{"name": r[0], "priority": r[1]} for r in rows]

    def get_cefr_distribution(
        self, lemma: str, pos: str, source_name: str,
    ) -> dict[str, float] | None:
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT distribution FROM cefr WHERE lemma=? AND pos=? AND source_name=?",
            (lemma.lower(), pos, source_name),
        ).fetchone()
        if row is None:
            row = self._conn.execute(
                "SELECT distribution FROM cefr WHERE lemma=? AND source_name=? LIMIT 1",
                (lemma.lower(), source_name),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])  # type: ignore[no-any-return]

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        if self._conn is None:
            return None, None
        row = self._conn.execute(
            "SELECT us_url, uk_url FROM audio WHERE lemma=?",
            (lemma.lower(),),
        ).fetchone()
        if row is None:
            return None, None
        return row[0], row[1]

    def get_ipa(self, lemma: str) -> tuple[str | None, str | None]:
        if self._conn is None:
            return None, None
        row = self._conn.execute(
            "SELECT us_ipa, uk_ipa FROM ipa WHERE lemma=?",
            (lemma.lower(),),
        ).fetchone()
        if row is None:
            return None, None
        return row[0], row[1]

    def get_usage_labels(self, lemma: str, pos: str) -> list[str] | None:
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT labels FROM usage WHERE lemma=? AND pos=?",
            (lemma.lower(), pos),
        ).fetchone()
        if row is None:
            row = self._conn.execute(
                "SELECT labels FROM usage WHERE lemma=? LIMIT 1",
                (lemma.lower(),),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])  # type: ignore[no-any-return]
