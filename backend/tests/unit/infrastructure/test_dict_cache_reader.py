from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.cli.build_dict_cache import build_cache
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


@pytest.fixture()
def reader(tmp_path: Path) -> DictCacheReader:
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
        assert dist is not None
        assert abs(dist["A1"] - 0.3) < 0.01
        assert abs(dist["A2"] - 0.7) < 0.01

    def test_unknown_word(self, reader: DictCacheReader) -> None:
        dist = reader.get_cefr_distribution("zzz", "verb", "Source A")
        assert dist is None

    def test_pos_fallback(self, reader: DictCacheReader) -> None:
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
