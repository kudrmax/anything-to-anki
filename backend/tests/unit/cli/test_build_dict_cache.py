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
        assert row is not None and len(row[0]) == 64
        conn.close()

    def test_atomic_replace(self, dictionaries_dir: Path) -> None:
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
        audio = json.loads((dictionaries_dir / "audio.json").read_text())
        audio["new_word"] = {"us": "https://example.com/new.mp3"}
        (dictionaries_dir / "audio.json").write_text(json.dumps(audio))
        assert is_cache_current(dictionaries_dir) is False
