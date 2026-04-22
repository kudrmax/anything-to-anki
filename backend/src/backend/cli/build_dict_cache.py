"""Build SQLite dictionary cache from unified JSON files.

Usage:
    python -m backend.cli.build_dict_cache /path/to/dictionaries
    python -m backend.cli.build_dict_cache /path/to/dictionaries --if-changed
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE cefr (
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    distribution TEXT NOT NULL,
    source_name TEXT NOT NULL,
    priority TEXT NOT NULL,
    PRIMARY KEY (lemma, pos, source_name)
);

CREATE TABLE audio (
    lemma TEXT PRIMARY KEY,
    us_url TEXT,
    uk_url TEXT
);

CREATE TABLE ipa (
    lemma TEXT PRIMARY KEY,
    us_ipa TEXT,
    uk_ipa TEXT
);

CREATE TABLE usage (
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    labels TEXT NOT NULL,
    PRIMARY KEY (lemma, pos)
);

CREATE TABLE build_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _compute_sources_hash(dictionaries_dir: Path) -> str:
    files: list[Path] = []
    cefr_dir = dictionaries_dir / "cefr"
    if cefr_dir.is_dir():
        files.extend(sorted(cefr_dir.glob("*.json")))
    for name in ("audio.json", "ipa.json", "usage.json"):
        p = dictionaries_dir / name
        if p.is_file():
            files.append(p)

    hasher = hashlib.sha256()
    for f in sorted(files):
        hasher.update(f.name.encode())
        hasher.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
    return hasher.hexdigest()


def _normalize_distribution(raw: dict[str, float]) -> dict[str, float]:
    total = sum(raw.values())
    if total <= 0:
        return raw
    return {k: v / total for k, v in raw.items()}


def _load_cefr(conn: sqlite3.Connection, dictionaries_dir: Path) -> int:
    cefr_dir = dictionaries_dir / "cefr"
    if not cefr_dir.is_dir():
        return 0
    count = 0
    for json_path in sorted(cefr_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        meta = data["meta"]
        source_name = meta["name"]
        priority = meta["priority"]
        for lemma, pos_dict in data["entries"].items():
            for pos, dist_raw in pos_dict.items():
                dist_normalized = _normalize_distribution(dist_raw)
                conn.execute(
                    "INSERT OR REPLACE INTO cefr (lemma, pos, distribution, source_name, priority) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (lemma.lower(), pos, json.dumps(dist_normalized), source_name, priority),
                )
                count += 1
    return count


def _load_audio(conn: sqlite3.Connection, dictionaries_dir: Path) -> int:
    path = dictionaries_dir / "audio.json"
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for lemma, urls in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO audio (lemma, us_url, uk_url) VALUES (?, ?, ?)",
            (lemma.lower(), urls.get("us"), urls.get("uk")),
        )
        count += 1
    return count


def _load_ipa(conn: sqlite3.Connection, dictionaries_dir: Path) -> int:
    path = dictionaries_dir / "ipa.json"
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for lemma, ipas in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO ipa (lemma, us_ipa, uk_ipa) VALUES (?, ?, ?)",
            (lemma.lower(), ipas.get("us"), ipas.get("uk")),
        )
        count += 1
    return count


def _load_usage(conn: sqlite3.Connection, dictionaries_dir: Path) -> int:
    path = dictionaries_dir / "usage.json"
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for lemma, pos_dict in data.items():
        for pos, labels in pos_dict.items():
            conn.execute(
                "INSERT OR REPLACE INTO usage (lemma, pos, labels) VALUES (?, ?, ?)",
                (lemma.lower(), pos, json.dumps(labels)),
            )
            count += 1
    return count


def build_cache(dictionaries_dir: Path) -> Path:
    cache_dir = dictionaries_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)
    db_path = cache_dir / "dict.db"
    tmp_path = cache_dir / "dict.db.tmp"

    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    conn.executescript(_SCHEMA)

    cefr_count = _load_cefr(conn, dictionaries_dir)
    audio_count = _load_audio(conn, dictionaries_dir)
    ipa_count = _load_ipa(conn, dictionaries_dir)
    usage_count = _load_usage(conn, dictionaries_dir)

    sources_hash = _compute_sources_hash(dictionaries_dir)
    conn.execute(
        "INSERT INTO build_meta (key, value) VALUES (?, ?)",
        ("sources_hash", sources_hash),
    )
    conn.execute(
        "INSERT INTO build_meta (key, value) VALUES (?, ?)",
        ("built_at", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    tmp_path.replace(db_path)

    logger.info(
        "Built dict.db: %d CEFR, %d audio, %d IPA, %d usage entries",
        cefr_count, audio_count, ipa_count, usage_count,
    )
    return db_path


def is_cache_current(dictionaries_dir: Path) -> bool:
    db_path = dictionaries_dir / ".cache" / "dict.db"
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT value FROM build_meta WHERE key='sources_hash'"
        ).fetchone()
        conn.close()
        if row is None:
            return False
        current_hash = _compute_sources_hash(dictionaries_dir)
        return row[0] == current_hash
    except sqlite3.Error:
        return False


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m backend.cli.build_dict_cache <dictionaries_dir> [--if-changed]")
        sys.exit(1)

    dictionaries_dir = Path(sys.argv[1])
    if_changed = "--if-changed" in sys.argv

    if if_changed and is_cache_current(dictionaries_dir):
        print("Dictionary cache is up to date.")
        return

    build_cache(dictionaries_dir)
    print("Dictionary cache rebuilt.")


if __name__ == "__main__":
    main()
