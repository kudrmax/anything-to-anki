from unittest.mock import patch

from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)
from backend.infrastructure.adapters.cambridge.pronunciation_source import (
    CambridgePronunciationSource,
)


def _make_word(
    word: str,
    us_audio: list[str] | None = None,
    uk_audio: list[str] | None = None,
) -> CambridgeWord:
    entry = CambridgeEntry(
        headword=word,
        pos=["noun"],
        uk_ipa=["/test/"],
        us_ipa=["/test/"],
        uk_audio=uk_audio or [],
        us_audio=us_audio or [],
        senses=[
            CambridgeSense(
                definition="test def",
                level="",
                examples=[],
                labels_and_codes=[],
                usages=[],
                domains=[],
                regions=[],
                image_link="",
            ),
        ],
    )
    return CambridgeWord(word=word, entries=[entry])


_PATCH_TARGET = (
    "backend.infrastructure.adapters.cambridge"
    ".pronunciation_source.parse_cambridge_jsonl"
)


class TestCambridgePronunciationSource:
    def test_returns_both_urls(self) -> None:
        data = {
            "hello": _make_word(
                "hello",
                us_audio=["https://cdn/us/hello.mp3"],
                uk_audio=["https://cdn/uk/hello.mp3"],
            ),
        }
        with patch(_PATCH_TARGET, return_value=data):
            source = CambridgePronunciationSource("/fake/path.jsonl")
        us, uk = source.get_audio_urls("hello")
        assert us == "https://cdn/us/hello.mp3"
        assert uk == "https://cdn/uk/hello.mp3"

    def test_returns_none_for_unknown_word(self) -> None:
        with patch(_PATCH_TARGET, return_value={}):
            source = CambridgePronunciationSource("/fake/path.jsonl")
        us, uk = source.get_audio_urls("nonexistent")
        assert us is None
        assert uk is None

    def test_returns_none_for_empty_audio(self) -> None:
        data = {"test": _make_word("test", us_audio=[], uk_audio=[])}
        with patch(_PATCH_TARGET, return_value=data):
            source = CambridgePronunciationSource("/fake/path.jsonl")
        us, uk = source.get_audio_urls("test")
        assert us is None
        assert uk is None

    def test_partial_audio_us_only(self) -> None:
        data = {
            "test": _make_word(
                "test",
                us_audio=["https://cdn/us.mp3"],
                uk_audio=[],
            ),
        }
        with patch(_PATCH_TARGET, return_value=data):
            source = CambridgePronunciationSource("/fake/path.jsonl")
        us, uk = source.get_audio_urls("test")
        assert us == "https://cdn/us.mp3"
        assert uk is None

    def test_takes_first_audio_url(self) -> None:
        data = {
            "test": _make_word(
                "test",
                us_audio=["https://cdn/us1.mp3", "https://cdn/us2.mp3"],
                uk_audio=["https://cdn/uk1.mp3"],
            ),
        }
        with patch(_PATCH_TARGET, return_value=data):
            source = CambridgePronunciationSource("/fake/path.jsonl")
        us, uk = source.get_audio_urls("test")
        assert us == "https://cdn/us1.mp3"
        assert uk == "https://cdn/uk1.mp3"
