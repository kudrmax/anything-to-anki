from __future__ import annotations

from typing import TYPE_CHECKING

from backend.infrastructure.adapters.cambridge.pronunciation_source import (
    CambridgePronunciationSource,
)
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader

from .conftest import create_cambridge_test_db

if TYPE_CHECKING:
    from pathlib import Path


def _make_source(tmp_path: Path, entries: list[dict[str, object]]) -> CambridgePronunciationSource:
    db_path = create_cambridge_test_db(tmp_path, entries)
    reader = CambridgeSQLiteReader(db_path)
    return CambridgePronunciationSource(reader)


class TestCambridgePronunciationSource:
    def test_returns_both_urls(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {
                "word": "hello",
                "us_audio": ["https://cdn/us/hello.mp3"],
                "uk_audio": ["https://cdn/uk/hello.mp3"],
            },
        ])
        us, uk = source.get_audio_urls("hello")
        assert us == "https://cdn/us/hello.mp3"
        assert uk == "https://cdn/uk/hello.mp3"

    def test_returns_none_for_unknown_word(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [])
        us, uk = source.get_audio_urls("nonexistent")
        assert us is None
        assert uk is None

    def test_returns_none_for_empty_audio(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {"word": "test", "us_audio": [], "uk_audio": []},
        ])
        us, uk = source.get_audio_urls("test")
        assert us is None
        assert uk is None

    def test_partial_audio_us_only(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {"word": "test", "us_audio": ["https://cdn/us.mp3"], "uk_audio": []},
        ])
        us, uk = source.get_audio_urls("test")
        assert us == "https://cdn/us.mp3"
        assert uk is None

    def test_takes_first_audio_url(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {
                "word": "test",
                "us_audio": ["https://cdn/us1.mp3", "https://cdn/us2.mp3"],
                "uk_audio": ["https://cdn/uk1.mp3"],
            },
        ])
        us, uk = source.get_audio_urls("test")
        assert us == "https://cdn/us1.mp3"
        assert uk == "https://cdn/uk1.mp3"
