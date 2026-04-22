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
