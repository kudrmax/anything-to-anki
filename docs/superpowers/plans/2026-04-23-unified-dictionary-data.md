# Unified Dictionary Data — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Отвязать проект от конкретных словарей (Cambridge, Oxford, EFLLex, Kelly), заменив их на unified JSON формат с SQLite-кэшем. Вынести скрейперы и конвертеры в отдельный репо.

**Architecture:** Четыре типа unified JSON (CEFR, audio, IPA, usage) → CLI `build_dict_cache` собирает SQLite кэш → новые адаптеры `dict_cache/*` читают через targeted SELECT → старые адаптеры удаляются. Конвертеры и скрейперы переезжают в репо `anything-to-anki-parsers`.

**Tech Stack:** Python, SQLite, JSON, Makefile

**Spec:** `docs/superpowers/specs/2026-04-23-unified-dictionary-data-design.md`

---

## Порядок выполнения

Задачи 1–10 выполняются в этом репо (anything-to-anki) в worktree.
Задача 11 — в репо anything-to-anki-parsers.

**Перед началом работы:** сделать бэкап текущих словарей:
```bash
cp -r dictionaries/ dictionaries_backup_2026-04-23/
```

---

### Task 1: pos_mapping — доменный сервис маппинга POS

Вынести маппинг Penn Treebank → unified POS из `sqlite_reader.py` в доменный сервис.

**Files:**
- Create: `backend/src/backend/domain/services/pos_mapping.py`
- Create: `backend/tests/unit/domain/test_pos_mapping.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/unit/domain/test_pos_mapping.py
from __future__ import annotations

from backend.domain.services.pos_mapping import map_pos_tag


class TestMapPosTag:
    def test_noun_tags(self) -> None:
        for tag in ("NN", "NNS", "NNP", "NNPS"):
            assert map_pos_tag(tag) == "noun"

    def test_verb_tags(self) -> None:
        for tag in ("VB", "VBD", "VBG", "VBN", "VBP", "VBZ"):
            assert map_pos_tag(tag) == "verb"

    def test_adjective_tags(self) -> None:
        for tag in ("JJ", "JJR", "JJS"):
            assert map_pos_tag(tag) == "adjective"

    def test_adverb_tags(self) -> None:
        for tag in ("RB", "RBR", "RBS"):
            assert map_pos_tag(tag) == "adverb"

    def test_other_tags(self) -> None:
        assert map_pos_tag("UH") == "exclamation"
        assert map_pos_tag("MD") == "modal verb"
        assert map_pos_tag("IN") == "preposition"
        assert map_pos_tag("DT") == "determiner"
        assert map_pos_tag("PRP") == "pronoun"
        assert map_pos_tag("PRP$") == "pronoun"
        assert map_pos_tag("CC") == "conjunction"

    def test_unknown_tag_returns_none(self) -> None:
        assert map_pos_tag("XYZ") is None
        assert map_pos_tag("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/domain/test_pos_mapping.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement pos_mapping.py**

```python
# backend/src/backend/domain/services/pos_mapping.py
"""Map Penn Treebank POS tags to unified dictionary POS names."""
from __future__ import annotations

_PTB_TO_UNIFIED: dict[str, str] = {
    "NN": "noun", "NNS": "noun", "NNP": "noun", "NNPS": "noun",
    "VB": "verb", "VBD": "verb", "VBG": "verb", "VBN": "verb",
    "VBP": "verb", "VBZ": "verb",
    "JJ": "adjective", "JJR": "adjective", "JJS": "adjective",
    "RB": "adverb", "RBR": "adverb", "RBS": "adverb",
    "UH": "exclamation", "MD": "modal verb",
    "IN": "preposition", "DT": "determiner",
    "PRP": "pronoun", "PRP$": "pronoun", "CC": "conjunction",
}


def map_pos_tag(ptb_tag: str) -> str | None:
    """Convert a Penn Treebank POS tag to unified dictionary POS.

    Returns None if the tag is not recognized.
    """
    return _PTB_TO_UNIFIED.get(ptb_tag)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/domain/test_pos_mapping.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/domain/services/pos_mapping.py backend/tests/unit/domain/test_pos_mapping.py
git commit -m "feat: add pos_mapping domain service"
```

---

### Task 2: UsageSource port

Создать ABC-порт для usage-данных. Сейчас `CambridgeUsageLookup` используется как конкретный класс без абстракции.

**Files:**
- Create: `backend/src/backend/domain/ports/usage_source.py`

- [ ] **Step 1: Create the port**

```python
# backend/src/backend/domain/ports/usage_source.py
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.value_objects.usage_distribution import UsageDistribution


class UsageSource(ABC):
    """Port for looking up usage labels by lemma and POS."""

    @abstractmethod
    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        """Return usage distribution for the given word.

        Returns UsageDistribution(None) if the word is not found.
        """
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/backend/domain/ports/usage_source.py
git commit -m "feat: add UsageSource port"
```

---

### Task 3: build_dict_cache CLI

CLI-скрипт, который читает unified JSON из `DICTIONARIES_DIR`, валидирует, строит `dict.db`.

**Files:**
- Create: `backend/src/backend/cli/__init__.py`
- Create: `backend/src/backend/cli/build_dict_cache.py`
- Create: `backend/tests/unit/cli/__init__.py`
- Create: `backend/tests/unit/cli/test_build_dict_cache.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/unit/cli/test_build_dict_cache.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.cli.build_dict_cache import build_cache, is_cache_current


@pytest.fixture()
def dictionaries_dir(tmp_path: Path) -> Path:
    """Create a minimal dictionaries dir with all 4 types."""
    cefr_dir = tmp_path / "cefr"
    cefr_dir.mkdir()

    # CEFR source 1 (high priority)
    (cefr_dir / "oxford.json").write_text(json.dumps({
        "meta": {"name": "Oxford 5000", "priority": "high"},
        "entries": {
            "abandon": {"verb": {"B2": 1.0}, "noun": {"C1": 1.0}},
            "run": {"verb": {"A1": 3.0, "A2": 7.0}},
        },
    }))

    # CEFR source 2 (normal priority)
    (cefr_dir / "efllex.json").write_text(json.dumps({
        "meta": {"name": "EFLLex", "priority": "normal"},
        "entries": {
            "abandon": {"verb": {"B1": 0.3, "B2": 0.7}},
        },
    }))

    # Audio
    (tmp_path / "audio.json").write_text(json.dumps({
        "abandon": {"us": "https://example.com/us.mp3", "uk": "https://example.com/uk.mp3"},
        "run": {"us": "https://example.com/run_us.mp3"},
    }))

    # IPA
    (tmp_path / "ipa.json").write_text(json.dumps({
        "abandon": {"us": "/əˈbæn.dən/", "uk": "/əˈbæn.dən/"},
    }))

    # Usage
    (tmp_path / "usage.json").write_text(json.dumps({
        "abandon": {"verb": ["formal"]},
        "gonna": {"verb": ["informal"]},
    }))

    return tmp_path


class TestBuildCache:
    def test_creates_db_with_all_tables(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)

        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert tables == {"cefr", "audio", "ipa", "usage", "build_meta"}
        conn.close()

    def test_cefr_entries_with_normalization(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        # Oxford "run" has raw freqs {A1: 3.0, A2: 7.0} → normalized {A1: 0.3, A2: 0.7}
        row = conn.execute(
            "SELECT distribution FROM cefr WHERE lemma='run' AND source_name='Oxford 5000'"
        ).fetchone()
        dist = json.loads(row[0])
        assert abs(dist["A1"] - 0.3) < 0.01
        assert abs(dist["A2"] - 0.7) < 0.01
        conn.close()

    def test_cefr_priority_stored(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        row = conn.execute(
            "SELECT priority FROM cefr WHERE lemma='abandon' AND source_name='Oxford 5000'"
        ).fetchone()
        assert row[0] == "high"

        row = conn.execute(
            "SELECT priority FROM cefr WHERE lemma='abandon' AND source_name='EFLLex'"
        ).fetchone()
        assert row[0] == "normal"
        conn.close()

    def test_audio_entries(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        row = conn.execute("SELECT us_url, uk_url FROM audio WHERE lemma='run'").fetchone()
        assert row[0] == "https://example.com/run_us.mp3"
        assert row[1] is None
        conn.close()

    def test_ipa_entries(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        row = conn.execute("SELECT us_ipa, uk_ipa FROM ipa WHERE lemma='abandon'").fetchone()
        assert row[0] == "/əˈbæn.dən/"
        conn.close()

    def test_usage_entries(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        row = conn.execute("SELECT labels FROM usage WHERE lemma='gonna' AND pos='verb'").fetchone()
        assert json.loads(row[0]) == ["informal"]
        conn.close()

    def test_build_meta_hash(self, dictionaries_dir: Path) -> None:
        db_path = build_cache(dictionaries_dir)
        conn = sqlite3.connect(db_path)

        row = conn.execute("SELECT value FROM build_meta WHERE key='sources_hash'").fetchone()
        assert row is not None and len(row[0]) == 64  # SHA256 hex
        conn.close()

    def test_atomic_replace(self, dictionaries_dir: Path) -> None:
        """Building twice replaces the DB atomically."""
        db_path_1 = build_cache(dictionaries_dir)
        mtime_1 = db_path_1.stat().st_mtime
        db_path_2 = build_cache(dictionaries_dir)
        assert db_path_2.stat().st_mtime >= mtime_1


class TestIsCacheCurrent:
    def test_no_db_returns_false(self, dictionaries_dir: Path) -> None:
        assert is_cache_current(dictionaries_dir) is False

    def test_fresh_db_returns_true(self, dictionaries_dir: Path) -> None:
        build_cache(dictionaries_dir)
        assert is_cache_current(dictionaries_dir) is True

    def test_modified_json_returns_false(self, dictionaries_dir: Path) -> None:
        build_cache(dictionaries_dir)
        # Modify a source file
        audio = json.loads((dictionaries_dir / "audio.json").read_text())
        audio["new_word"] = {"us": "https://example.com/new.mp3"}
        (dictionaries_dir / "audio.json").write_text(json.dumps(audio))
        assert is_cache_current(dictionaries_dir) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/cli/test_build_dict_cache.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement build_dict_cache.py**

```python
# backend/src/backend/cli/__init__.py
```

```python
# backend/src/backend/cli/build_dict_cache.py
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
    """SHA256 of all JSON source files, sorted by name."""
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
    """Normalize raw frequency weights to sum=1.0."""
    total = sum(raw.values())
    if total <= 0:
        return raw
    return {k: v / total for k, v in raw.items()}


def _load_cefr(conn: sqlite3.Connection, dictionaries_dir: Path) -> int:
    """Load all CEFR JSON files into the cefr table. Returns row count."""
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
    """Build dict.db from unified JSON files. Returns path to dict.db."""
    cache_dir = dictionaries_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)
    db_path = cache_dir / "dict.db"
    tmp_path = cache_dir / "dict.db.tmp"

    # Remove leftover tmp
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
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO build_meta (key, value) VALUES (?, ?)",
        ("built_at", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    # Atomic replace
    tmp_path.replace(db_path)

    logger.info(
        "Built dict.db: %d CEFR, %d audio, %d IPA, %d usage entries",
        cefr_count, audio_count, ipa_count, usage_count,
    )
    return db_path


def is_cache_current(dictionaries_dir: Path) -> bool:
    """Check if dict.db is up-to-date with JSON sources."""
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
```

Также создать `__init__.py`:
```python
# backend/tests/unit/cli/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/cli/test_build_dict_cache.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/cli/ backend/tests/unit/cli/
git commit -m "feat: add build_dict_cache CLI for SQLite dictionary cache"
```

---

### Task 4: DictCacheReader

Read-only SQLite reader для dict.db. Singleton, аналог текущего `CambridgeSQLiteReader`.

**Files:**
- Create: `backend/src/backend/infrastructure/adapters/dict_cache/__init__.py`
- Create: `backend/src/backend/infrastructure/adapters/dict_cache/reader.py`
- Create: `backend/tests/unit/infrastructure/test_dict_cache_reader.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/unit/infrastructure/test_dict_cache_reader.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.cli.build_dict_cache import build_cache
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


@pytest.fixture()
def reader(tmp_path: Path) -> DictCacheReader:
    """Build a dict.db from fixtures and return a reader."""
    cefr_dir = tmp_path / "cefr"
    cefr_dir.mkdir()
    (cefr_dir / "src1.json").write_text(json.dumps({
        "meta": {"name": "Source A", "priority": "high"},
        "entries": {
            "abandon": {"verb": {"B2": 1.0}},
            "run": {"verb": {"A1": 3.0, "A2": 7.0}},
        },
    }))
    (cefr_dir / "src2.json").write_text(json.dumps({
        "meta": {"name": "Source B", "priority": "normal"},
        "entries": {"abandon": {"verb": {"B1": 0.3, "B2": 0.7}}},
    }))
    (tmp_path / "audio.json").write_text(json.dumps({
        "abandon": {"us": "https://a.com/us.mp3", "uk": "https://a.com/uk.mp3"},
        "run": {"us": "https://a.com/run.mp3"},
    }))
    (tmp_path / "ipa.json").write_text(json.dumps({
        "abandon": {"us": "/əˈbæn.dən/", "uk": "/əˈbæn.dən/"},
    }))
    (tmp_path / "usage.json").write_text(json.dumps({
        "abandon": {"verb": ["formal"]},
    }))

    build_cache(tmp_path)
    return DictCacheReader(tmp_path / ".cache" / "dict.db")


class TestGetCEFRSources:
    def test_returns_all_sources_with_priority(self, reader: DictCacheReader) -> None:
        sources = reader.get_cefr_sources()
        names = {s["name"] for s in sources}
        assert names == {"Source A", "Source B"}
        by_name = {s["name"]: s for s in sources}
        assert by_name["Source A"]["priority"] == "high"
        assert by_name["Source B"]["priority"] == "normal"


class TestGetCEFRDistribution:
    def test_known_word(self, reader: DictCacheReader) -> None:
        dist = reader.get_cefr_distribution("abandon", "verb", "Source A")
        assert dist == {"B2": 1.0}

    def test_normalized_distribution(self, reader: DictCacheReader) -> None:
        dist = reader.get_cefr_distribution("run", "verb", "Source A")
        assert abs(dist["A1"] - 0.3) < 0.01
        assert abs(dist["A2"] - 0.7) < 0.01

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        dist = reader.get_cefr_distribution("zzz", "verb", "Source A")
        assert dist is None

    def test_pos_fallback(self, reader: DictCacheReader) -> None:
        # "abandon" has only "verb", querying "noun" should fallback to any POS
        dist = reader.get_cefr_distribution("abandon", "noun", "Source A")
        assert dist is not None


class TestGetAudioUrls:
    def test_both_urls(self, reader: DictCacheReader) -> None:
        us, uk = reader.get_audio_urls("abandon")
        assert us == "https://a.com/us.mp3"
        assert uk == "https://a.com/uk.mp3"

    def test_partial_urls(self, reader: DictCacheReader) -> None:
        us, uk = reader.get_audio_urls("run")
        assert us == "https://a.com/run.mp3"
        assert uk is None

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        us, uk = reader.get_audio_urls("zzz")
        assert us is None and uk is None


class TestGetIPA:
    def test_known(self, reader: DictCacheReader) -> None:
        us, uk = reader.get_ipa("abandon")
        assert us == "/əˈbæn.dən/"

    def test_unknown(self, reader: DictCacheReader) -> None:
        us, uk = reader.get_ipa("zzz")
        assert us is None and uk is None


class TestGetUsageLabels:
    def test_known(self, reader: DictCacheReader) -> None:
        labels = reader.get_usage_labels("abandon", "verb")
        assert labels == ["formal"]

    def test_unknown(self, reader: DictCacheReader) -> None:
        labels = reader.get_usage_labels("zzz", "verb")
        assert labels is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/infrastructure/test_dict_cache_reader.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement DictCacheReader**

```python
# backend/src/backend/infrastructure/adapters/dict_cache/__init__.py
```

```python
# backend/src/backend/infrastructure/adapters/dict_cache/reader.py
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
        """Return list of {name, priority} for all CEFR sources in the cache."""
        if self._conn is None:
            return []
        rows = self._conn.execute(
            "SELECT DISTINCT source_name, priority FROM cefr"
        ).fetchall()
        return [{"name": r[0], "priority": r[1]} for r in rows]

    def get_cefr_distribution(
        self, lemma: str, pos: str, source_name: str,
    ) -> dict[str, float] | None:
        """Return normalized CEFR distribution for a word from a specific source.

        Falls back to any POS if exact POS match not found.
        """
        if self._conn is None:
            return None

        # Try exact POS match
        row = self._conn.execute(
            "SELECT distribution FROM cefr WHERE lemma=? AND pos=? AND source_name=?",
            (lemma.lower(), pos, source_name),
        ).fetchone()

        # Fallback: any POS for this source
        if row is None:
            row = self._conn.execute(
                "SELECT distribution FROM cefr WHERE lemma=? AND source_name=? LIMIT 1",
                (lemma.lower(), source_name),
            ).fetchone()

        if row is None:
            return None
        return json.loads(row[0])

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        """Return (us_url, uk_url) for the given lemma."""
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
        """Return (us_ipa, uk_ipa) for the given lemma."""
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
        """Return usage labels for the given lemma and POS.

        Falls back to any POS if exact match not found.
        """
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
        return json.loads(row[0])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/infrastructure/test_dict_cache_reader.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/infrastructure/adapters/dict_cache/
git add backend/tests/unit/infrastructure/test_dict_cache_reader.py
git commit -m "feat: add DictCacheReader for unified dictionary SQLite cache"
```

---

### Task 5: Адаптеры dict_cache — CEFRSource, PronunciationSource, UsageSource

Три адаптера, реализующие существующие порты через `DictCacheReader`.

**Files:**
- Create: `backend/src/backend/infrastructure/adapters/dict_cache/cefr_source.py`
- Create: `backend/src/backend/infrastructure/adapters/dict_cache/pronunciation_source.py`
- Create: `backend/src/backend/infrastructure/adapters/dict_cache/usage_source.py`
- Create: `backend/tests/unit/infrastructure/test_dict_cache_adapters.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/unit/infrastructure/test_dict_cache_adapters.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.cli.build_dict_cache import build_cache
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.pronunciation_source import DictCachePronunciationSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader
from backend.infrastructure.adapters.dict_cache.usage_source import DictCacheUsageSource


@pytest.fixture()
def reader(tmp_path: Path) -> DictCacheReader:
    cefr_dir = tmp_path / "cefr"
    cefr_dir.mkdir()
    (cefr_dir / "src.json").write_text(json.dumps({
        "meta": {"name": "TestDict", "priority": "high"},
        "entries": {"abandon": {"verb": {"B2": 1.0}}},
    }))
    (tmp_path / "audio.json").write_text(json.dumps({
        "abandon": {"us": "https://a.com/us.mp3", "uk": "https://a.com/uk.mp3"},
    }))
    (tmp_path / "ipa.json").write_text(json.dumps({}))
    (tmp_path / "usage.json").write_text(json.dumps({
        "abandon": {"verb": ["formal", "disapproving"]},
    }))
    build_cache(tmp_path)
    return DictCacheReader(tmp_path / ".cache" / "dict.db")


class TestDictCacheCEFRSource:
    def test_name(self, reader: DictCacheReader) -> None:
        src = DictCacheCEFRSource(reader, "TestDict")
        assert src.name == "TestDict"

    def test_known_word(self, reader: DictCacheReader) -> None:
        src = DictCacheCEFRSource(reader, "TestDict")
        dist = src.get_distribution("abandon", "VB")
        assert dist == {CEFRLevel.B2: 1.0}

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        src = DictCacheCEFRSource(reader, "TestDict")
        dist = src.get_distribution("zzz", "NN")
        assert dist == {CEFRLevel.UNKNOWN: 1.0}


class TestDictCachePronunciationSource:
    def test_known_word(self, reader: DictCacheReader) -> None:
        src = DictCachePronunciationSource(reader)
        us, uk = src.get_audio_urls("abandon")
        assert us == "https://a.com/us.mp3"
        assert uk == "https://a.com/uk.mp3"

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        src = DictCachePronunciationSource(reader)
        us, uk = src.get_audio_urls("zzz")
        assert us is None and uk is None


class TestDictCacheUsageSource:
    def test_known_word(self, reader: DictCacheReader) -> None:
        src = DictCacheUsageSource(reader)
        dist = src.get_distribution("abandon", "VB")
        assert dist.groups is not None
        assert "formal" in dist.groups
        assert "disapproving" in dist.groups

    def test_equal_weights(self, reader: DictCacheReader) -> None:
        src = DictCacheUsageSource(reader)
        dist = src.get_distribution("abandon", "VB")
        assert dist.groups is not None
        assert abs(dist.groups["formal"] - 0.5) < 0.01
        assert abs(dist.groups["disapproving"] - 0.5) < 0.01

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        src = DictCacheUsageSource(reader)
        dist = src.get_distribution("zzz", "NN")
        assert dist.groups is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/infrastructure/test_dict_cache_adapters.py -v`
Expected: FAIL

- [ ] **Step 3: Implement the three adapters**

```python
# backend/src/backend/infrastructure/adapters/dict_cache/cefr_source.py
"""CEFRSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.pos_mapping import map_pos_tag
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCacheCEFRSource(CEFRSource):
    """CEFR source reading from the unified dict.db cache."""

    def __init__(self, reader: DictCacheReader, source_name: str) -> None:
        self._reader = reader
        self._source_name = source_name

    @property
    def name(self) -> str:
        return self._source_name

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        unified_pos = map_pos_tag(pos_tag) or pos_tag
        raw = self._reader.get_cefr_distribution(lemma, unified_pos, self._source_name)
        if raw is None:
            return {CEFRLevel.UNKNOWN: 1.0}
        return {CEFRLevel.from_str(k): v for k, v in raw.items()}
```

```python
# backend/src/backend/infrastructure/adapters/dict_cache/pronunciation_source.py
"""PronunciationSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.pronunciation_source import PronunciationSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCachePronunciationSource(PronunciationSource):
    """Audio URL lookup from the unified dict.db cache."""

    def __init__(self, reader: DictCacheReader) -> None:
        self._reader = reader

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        return self._reader.get_audio_urls(lemma)
```

```python
# backend/src/backend/infrastructure/adapters/dict_cache/usage_source.py
"""UsageSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.usage_source import UsageSource
from backend.domain.services.pos_mapping import map_pos_tag
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCacheUsageSource(UsageSource):
    """Usage lookup from the unified dict.db cache.

    Labels are passed through as-is — no transformation.
    Each label gets equal weight in the distribution.
    """

    def __init__(self, reader: DictCacheReader) -> None:
        self._reader = reader

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        unified_pos = map_pos_tag(pos_tag) or pos_tag
        labels = self._reader.get_usage_labels(lemma, unified_pos)
        if labels is None or not labels:
            return UsageDistribution(None)
        weight = 1.0 / len(labels)
        groups = {label: weight for label in labels}
        return UsageDistribution(groups)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/infrastructure/test_dict_cache_adapters.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/infrastructure/adapters/dict_cache/cefr_source.py
git add backend/src/backend/infrastructure/adapters/dict_cache/pronunciation_source.py
git add backend/src/backend/infrastructure/adapters/dict_cache/usage_source.py
git add backend/tests/unit/infrastructure/test_dict_cache_adapters.py
git commit -m "feat: add dict_cache adapters for CEFR, pronunciation, usage"
```

---

### Task 6: Убрать хардкод из cefr_level_resolver

Заменить `PRIORITY_SOURCE_NAMES = ["Oxford 5000", "Cambridge Dictionary"]` на динамическое определение priority через списки, переданные из `VotingCEFRClassifier`.

**Files:**
- Modify: `backend/src/backend/domain/services/cefr_level_resolver.py`
- Modify: `backend/src/backend/domain/services/voting_cefr_classifier.py`
- Modify: `backend/tests/unit/domain/test_cefr_level_resolver.py`

- [ ] **Step 1: Read current test file**

Run: `cat backend/tests/unit/domain/test_cefr_level_resolver.py`

Нужно понять текущие тесты, чтобы обновить их.

- [ ] **Step 2: Update cefr_level_resolver.py**

Заменить хардкод имён на работу со списками priority/regular votes, которые уже передаются отдельно через `VotingCEFRClassifier`:

```python
# backend/src/backend/domain/services/cefr_level_resolver.py
"""Resolve final CEFR level from source votes.

Pure domain logic, no I/O. Encodes the priority strategy:
min(priority_votes) → whichever is available → weighted voting among regular.
"""
from __future__ import annotations

from collections import defaultdict

from backend.domain.value_objects.cefr_breakdown import SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


def resolve_cefr_level(
    priority_votes: list[SourceVote],
    regular_votes: list[SourceVote],
) -> tuple[CEFRLevel, str]:
    """Determine final CEFR level from source votes.

    Strategy:
    1. Collect known levels from priority sources.
    2. If 2+ priority sources know the word → take the lower (easier) level.
    3. If exactly 1 knows → take that one.
    4. If none know → equal-weight voting among regular sources.

    Returns (level, decision_method).
    """
    known_priority = [
        v.top_level for v in priority_votes
        if v.top_level is not CEFRLevel.UNKNOWN
    ]

    if known_priority:
        level = min(known_priority, key=lambda lvl: lvl.value)
        return level, "priority"

    if not regular_votes:
        return CEFRLevel.UNKNOWN, "voting"

    non_unknown = [v for v in regular_votes if v.top_level is not CEFRLevel.UNKNOWN]
    if not non_unknown:
        return CEFRLevel.UNKNOWN, "voting"

    return _weighted_vote(non_unknown), "voting"


def _weighted_vote(votes: list[SourceVote]) -> CEFRLevel:
    """Equal-weight voting. Tie-break: prefer lower (easier) level."""
    weight = 1.0 / len(votes)
    totals: dict[CEFRLevel, float] = defaultdict(float)
    for vote in votes:
        for level, prob in vote.distribution.items():
            totals[level] += prob * weight
    return max(totals, key=lambda lvl: (totals[lvl], -lvl.value))
```

- [ ] **Step 3: Update VotingCEFRClassifier to pass separate lists**

В `voting_cefr_classifier.py` изменить вызов `resolve_cefr_level`:

Заменить:
```python
final_level, decision_method = resolve_cefr_level(all_votes)
```
На:
```python
final_level, decision_method = resolve_cefr_level(priority_votes, votes)
```

- [ ] **Step 4: Update tests for new signature**

Обновить `test_cefr_level_resolver.py` — все вызовы `resolve_cefr_level` теперь принимают два списка вместо одного. Обновить `test_voting_cefr_classifier.py` — убрать ожидания конкретных имён "Oxford 5000", "Cambridge Dictionary".

- [ ] **Step 5: Run all CEFR tests**

Run: `cd backend && python -m pytest tests/unit/domain/test_cefr_level_resolver.py tests/unit/domain/test_voting_cefr_classifier.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/backend/domain/services/cefr_level_resolver.py
git add backend/src/backend/domain/services/voting_cefr_classifier.py
git add backend/tests/unit/domain/test_cefr_level_resolver.py
git add backend/tests/unit/domain/test_voting_cefr_classifier.py
git commit -m "refactor: remove hardcoded priority source names from CEFR resolver"
```

---

### Task 7: Перевязать container.py и analyze_text.py

Заменить все старые адаптеры на новые в DI-контейнере. Заменить `CambridgeUsageLookup` на `UsageSource` в `analyze_text.py`.

**Files:**
- Modify: `backend/src/backend/infrastructure/container.py`
- Modify: `backend/src/backend/application/use_cases/analyze_text.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update container.py**

Заменить строки 131–154 (определение dictionaries_dir и все адаптеры):

Удалить импорты:
```python
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.pronunciation_source import CambridgePronunciationSource
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource
```

Добавить импорты:
```python
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.pronunciation_source import DictCachePronunciationSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader
from backend.infrastructure.adapters.dict_cache.usage_source import DictCacheUsageSource
```

Заменить блок создания адаптеров:
```python
        # Dictionary cache
        dictionaries_dir_env = os.environ.get("DICTIONARIES_DIR")
        if dictionaries_dir_env:
            dict_cache_path = Path(dictionaries_dir_env) / ".cache" / "dict.db"
        else:
            project_root = Path(__file__).resolve().parents[4]
            dictionaries_dir = project_root / "dictionaries"
            if not dictionaries_dir.exists():
                dictionaries_dir = Path("/app/dictionaries")
            dict_cache_path = dictionaries_dir / ".cache" / "dict.db"

        self._dict_reader = DictCacheReader(dict_cache_path)

        # CEFR: dynamic sources from dict.db metadata
        cefr_sources: list[CEFRSource] = []
        priority_sources: list[CEFRSource] = []
        for meta in self._dict_reader.get_cefr_sources():
            src = DictCacheCEFRSource(self._dict_reader, meta["name"])
            if meta["priority"] == "high":
                priority_sources.append(src)
            else:
                cefr_sources.append(src)
        cefr_sources.append(CefrpyCEFRSource())  # built-in fallback

        self._cefr_classifier = VotingCEFRClassifier(
            cefr_sources,
            priority_sources=priority_sources,
        )

        self._pronunciation_source = DictCachePronunciationSource(self._dict_reader)
        self._usage_source = DictCacheUsageSource(self._dict_reader)
```

Заменить `usage_lookup=self._cambridge_usage_lookup` на `usage_lookup=self._usage_source` в `analyze_text_use_case` property.

- [ ] **Step 2: Update analyze_text.py**

Заменить тип `CambridgeUsageLookup` на `UsageSource`:

```python
# Было:
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup
# ...
usage_lookup: CambridgeUsageLookup | None = None,

# Стало:
from backend.domain.ports.usage_source import UsageSource
# ...
usage_lookup: UsageSource | None = None,
```

Вся остальная логика в `analyze_text.py` остаётся — `usage_lookup.get_distribution(lemma, pos_tag)` вызывается одинаково.

- [ ] **Step 3: Add DICTIONARIES_DIR to .env.example**

Добавить в `.env.example`:
```env
# Путь к папке с unified-словарями (JSON файлы).
# По умолчанию: dictionaries/ в корне проекта.
# DICTIONARIES_DIR=./dictionaries
```

- [ ] **Step 4: Update docker-compose.yml volumes**

Изменить volume mount — теперь `.cache/` внутри dictionaries должна быть writable при сборке кэша. Но dict.db собирается ДО запуска контейнеров (через make), а контейнер читает read-only. Оставить `:ro`.

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest --timeout=30 -x -q`
Expected: тесты, зависящие от старых адаптеров, упадут — это ожидаемо, починим в Task 8.

- [ ] **Step 6: Commit**

```bash
git add backend/src/backend/infrastructure/container.py
git add backend/src/backend/application/use_cases/analyze_text.py
git add .env.example docker-compose.yml
git commit -m "refactor: wire dict_cache adapters in container, replace CambridgeUsageLookup with UsageSource"
```

---

### Task 8: Удалить старые адаптеры и обновить тесты

Удалить все Cambridge/Oxford/EFLLex/Kelly адаптеры. Удалить или переписать зависимые тесты.

**Files:**
- Delete: `backend/src/backend/infrastructure/adapters/cambridge/` (весь пакет)
- Delete: `backend/src/backend/infrastructure/adapters/oxford_cefr_source.py`
- Delete: `backend/src/backend/infrastructure/adapters/efllex_cefr_source.py`
- Delete: `backend/src/backend/infrastructure/adapters/kelly_cefr_source.py`
- Delete тесты старых адаптеров:
  - `backend/tests/unit/infrastructure/test_cambridge_cefr_source.py`
  - `backend/tests/unit/infrastructure/test_cambridge_pronunciation_source.py`
  - `backend/tests/unit/infrastructure/test_cambridge_sqlite_reader.py`
  - `backend/tests/unit/infrastructure/test_cambridge_usage_groups.py`
  - `backend/tests/unit/infrastructure/test_cambridge_usage_lookup.py`
  - `backend/tests/integration/test_cambridge_jsonl_format.py`
  - `backend/tests/integration/test_efllex_cefr_source.py`
  - `backend/tests/integration/test_kelly_cefr_source.py`
  - `backend/tests/integration/test_oxford_cefr_source.py`
- Update: `backend/tests/integration/test_cefrpy_classifier.py` — убрать зависимости от старых источников
- Update: `backend/tests/integration/test_usage_sorting_pipeline.py` — использовать DictCacheUsageSource

- [ ] **Step 1: Delete old adapter files**

```bash
trash backend/src/backend/infrastructure/adapters/cambridge/
trash backend/src/backend/infrastructure/adapters/oxford_cefr_source.py
trash backend/src/backend/infrastructure/adapters/efllex_cefr_source.py
trash backend/src/backend/infrastructure/adapters/kelly_cefr_source.py
```

- [ ] **Step 2: Delete old adapter tests**

```bash
trash backend/tests/unit/infrastructure/test_cambridge_cefr_source.py
trash backend/tests/unit/infrastructure/test_cambridge_pronunciation_source.py
trash backend/tests/unit/infrastructure/test_cambridge_sqlite_reader.py
trash backend/tests/unit/infrastructure/test_cambridge_usage_groups.py
trash backend/tests/unit/infrastructure/test_cambridge_usage_lookup.py
trash backend/tests/integration/test_cambridge_jsonl_format.py
trash backend/tests/integration/test_efllex_cefr_source.py
trash backend/tests/integration/test_kelly_cefr_source.py
trash backend/tests/integration/test_oxford_cefr_source.py
```

- [ ] **Step 3: Update remaining integration tests**

Обновить `test_cefrpy_classifier.py` — убрать создание Oxford/Cambridge/EFLLex/Kelly источников, оставить только CefrpyCEFRSource + DictCacheCEFRSource с тестовыми JSON-фикстурами.

Обновить `test_usage_sorting_pipeline.py` — заменить `CambridgeUsageLookup` на `DictCacheUsageSource`.

Grep для оставшихся ссылок на удалённые модули:
```bash
cd backend && grep -r "cambridge" src/ tests/ --include="*.py" -l
cd backend && grep -r "oxford_cefr\|efllex_cefr\|kelly_cefr" src/ tests/ --include="*.py" -l
```

Починить все найденные ссылки.

- [ ] **Step 4: Run full test suite**

Run: `cd backend && python -m pytest --timeout=30 -x -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old dictionary adapters (Cambridge, Oxford, EFLLex, Kelly)"
```

---

### Task 9: Makefile, README, .gitignore

Добавить make-команды для управления кэшем. Создать README с форматами. Обновить .gitignore.

**Files:**
- Modify: `Makefile`
- Modify: `.gitignore`
- Create: `dictionaries/README.md`

- [ ] **Step 1: Add make targets**

Добавить в Makefile перед таргетом `up`:

```makefile
dict-rebuild:  ## Пересобрать словарный кэш с нуля
	@rm -f $${DICTIONARIES_DIR:-.}/dictionaries/.cache/dict.db 2>/dev/null; \
	python -m backend.cli.build_dict_cache $${DICTIONARIES_DIR:-dictionaries}

dict-update:  ## Обновить словарный кэш если JSON изменились
	@python -m backend.cli.build_dict_cache $${DICTIONARIES_DIR:-dictionaries} --if-changed
```

В таргет `up` добавить вызов `dict-update` перед `docker compose`:

```makefile
up: _check_env dict-update  ## Запустить (ai_proxy + docker compose)
```

Аналогично для `up-worktree`.

- [ ] **Step 2: Update .gitignore**

Добавить:
```
dictionaries/.cache/
dictionaries_backup_*/
```

- [ ] **Step 3: Create dictionaries/README.md**

Создать README с полным описанием форматов, шаблонами для всех 4 типов данных, инструкцией по добавлению своего словаря и командами пересборки кэша. Содержание — как описано в спеке (секция "README с форматами").

- [ ] **Step 4: Commit**

```bash
git add Makefile .gitignore dictionaries/README.md
git commit -m "feat: add dict cache make targets and dictionaries README"
```

---

### Task 10: Удалить старые данные, переструктурировать dictionaries/

Удалить raw-файлы словарей из этого репо (они переедут в репо 3). Создать структуру для unified-файлов.

**Важно:** перед этим шагом убедиться, что бэкап `dictionaries_backup_2026-04-23/` существует.

**Files:**
- Delete: `dictionaries/cambridge.db`
- Delete: `dictionaries/cambridge.jsonl`
- Delete: `dictionaries/cefr/` (oxford5000.csv, efllex.tsv, kelly.csv)
- Delete: `scripts/scrapers/cambridge/` (переедет в репо 2)
- Modify: `Makefile` — убрать symlink на `dictionaries` в `up-worktree` (теперь пользователь указывает `DICTIONARIES_DIR`)

- [ ] **Step 1: Verify backup exists**

```bash
ls dictionaries_backup_2026-04-23/
```

- [ ] **Step 2: Delete old data files**

```bash
trash dictionaries/cambridge.db
trash dictionaries/cambridge.jsonl
trash dictionaries/cefr/
trash dictionaries/archive/
trash scripts/scrapers/cambridge/
```

- [ ] **Step 3: Remove git submodule if dictionaries is a submodule**

Проверить `dictionaries/.git` — если это submodule, отвязать:
```bash
git submodule deinit dictionaries
git rm dictionaries
```

Создать обычную директорию `dictionaries/` с README.

- [ ] **Step 4: Update Makefile up-worktree**

Убрать блок symlink на dictionaries (строки 98-115 в Makefile). Вместо этого worktree использует `DICTIONARIES_DIR` из `.env`.

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest --timeout=30 -x -q`
Expected: all PASS (тесты не зависят от raw файлов)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old dictionary data files and scraper scripts"
```

---

### Task 11: Конвертеры в репо anything-to-anki-parsers

Перенести скрейпер и создать конвертеры raw → unified в отдельном репо.

**Repo:** `https://github.com/kudrmax/anything-to-anki-parsers.git`

**Files:**
- Move: `scripts/scrapers/cambridge/` → `scrapers/cambridge/`
- Create: `converters/cambridge_to_unified.py`
- Create: `converters/oxford_to_unified.py`
- Create: `converters/efllex_to_unified.py`
- Create: `converters/kelly_to_unified.py`

- [ ] **Step 1: Clone repo and set up structure**

```bash
git clone https://github.com/kudrmax/anything-to-anki-parsers.git /tmp/anything-to-anki-parsers
cd /tmp/anything-to-anki-parsers
mkdir -p scrapers converters
```

- [ ] **Step 2: Move scraper**

Скопировать файлы из бэкапа (или из текущего репо до удаления):
```
scrapers/cambridge/run_scrape.py
scrapers/cambridge/scraper.py
scrapers/cambridge/convert_jsonl_to_sqlite.py  # оставить для обратной совместимости
scrapers/cambridge/requirements.txt
```

- [ ] **Step 3: Create cambridge_to_unified.py**

Конвертер `raw/cambridge.jsonl` → 4 unified JSON файла:
- `unified/cefr/cambridge.json` — для каждого entry: lemma + POS → CEFR первого sense. Priority: `"high"`
- `unified/audio.json` — lemma → первый US/UK audio URL
- `unified/ipa.json` — lemma → первый US/UK IPA
- `unified/usage.json` — lemma + POS → нормализованные labels

Нормализация usage: перенести логику из `usage_groups.py` (маппинг raw Cambridge labels → группы: `"infml"` → `"informal"`, `"disapproving"` → `"disapproving"` и т.д.).

POS маппинг: Cambridge JSON хранит POS как `["verb"]`, `["noun"]` — уже в unified формате, просто извлечь.

CLI:
```bash
python converters/cambridge_to_unified.py \
  --input raw/cambridge.jsonl \
  --output-dir unified/
```

- [ ] **Step 4: Create oxford_to_unified.py**

Конвертер `raw/oxford5000.csv` → `unified/cefr/oxford.json`.
POS маппинг: Oxford CSV хранит `type` как `verb`, `noun`, `adjective` — уже unified.
Priority: `"high"`.

```bash
python converters/oxford_to_unified.py \
  --input raw/oxford5000.csv \
  --output unified/cefr/oxford.json
```

- [ ] **Step 5: Create efllex_to_unified.py**

Конвертер `raw/efllex.tsv` → `unified/cefr/efllex.json`.
EFLLex хранит сырые частоты — записать as-is (нормализация при сборке кэша).
POS маппинг: EFLLex использует Penn Treebank теги (`NN`, `VB`) → конвертировать в unified (`noun`, `verb`).
Priority: `"normal"`.

```bash
python converters/efllex_to_unified.py \
  --input raw/efllex.tsv \
  --output unified/cefr/efllex.json
```

- [ ] **Step 6: Create kelly_to_unified.py**

Конвертер `raw/kelly.csv` → `unified/cefr/kelly.json`.
POS маппинг: Kelly CSV хранит `Part of Speech` как `Verb`, `Noun` → lowercase → unified.
Priority: `"normal"`.

```bash
python converters/kelly_to_unified.py \
  --input raw/kelly.csv \
  --output unified/cefr/kelly.json
```

- [ ] **Step 7: Create Makefile**

```makefile
convert-all:  ## Конвертировать все raw → unified
	python converters/cambridge_to_unified.py --input raw/cambridge.jsonl --output-dir unified/
	python converters/oxford_to_unified.py --input raw/oxford5000.csv --output unified/cefr/oxford.json
	python converters/efllex_to_unified.py --input raw/efllex.tsv --output unified/cefr/efllex.json
	python converters/kelly_to_unified.py --input raw/kelly.csv --output unified/cefr/kelly.json

scrape-cambridge:  ## Запустить скрейпер Cambridge Dictionary
	python scrapers/cambridge/run_scrape.py
```

- [ ] **Step 8: Create README.md**

Описание репо, инструкции по запуску скрейперов и конвертеров, описание форматов.

- [ ] **Step 9: Commit and push**

```bash
git add -A
git commit -m "feat: add scrapers and unified format converters"
git push
```

---

## Проверка после всех задач

После выполнения всех задач:

1. **В anything-to-anki:** `make dict-rebuild && make up && make logs` — проект запускается, логи чистые
2. **В anything-to-anki-parsers:** `make convert-all` — генерирует unified JSON
3. **Тесты:** `cd backend && python -m pytest` — все проходят
4. **Линтер:** `make lint` — чисто
5. **E2E:** открыть UI, загрузить источник, проверить что CEFR/audio/usage работают
