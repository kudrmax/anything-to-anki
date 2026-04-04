import pytest
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner


@pytest.mark.integration
class TestRegexTextCleaner:
    def setup_method(self) -> None:
        self.cleaner = RegexTextCleaner()

    def test_removes_timecodes(self) -> None:
        text = "[00:01:23] Hello world [1:23] foo"
        result = self.cleaner.clean(text)
        assert "[00:01:23]" not in result
        assert "[1:23]" not in result
        assert "Hello world" in result

    def test_removes_service_tags(self) -> None:
        text = "[Music] Hello [Applause] world [Laughter]"
        result = self.cleaner.clean(text)
        assert "[Music]" not in result
        assert "[Applause]" not in result
        assert "Hello" in result
        assert "world" in result

    def test_removes_music_symbols(self) -> None:
        text = "♪ Singing ♫ along ♪♪"
        result = self.cleaner.clean(text)
        assert "♪" not in result
        assert "Singing" in result

    def test_removes_duplicate_lines(self) -> None:
        text = "Hello world\nHello world\nGoodbye"
        result = self.cleaner.clean(text)
        assert result.count("Hello world") == 1
        assert "Goodbye" in result

    def test_normalizes_whitespace(self) -> None:
        text = "Hello   world\t\tfoo"
        result = self.cleaner.clean(text)
        assert "  " not in result
        assert result == "Hello world foo"

    def test_removes_bom(self) -> None:
        text = "\ufeffHello world"
        result = self.cleaner.clean(text)
        assert result == "Hello world"

    def test_preserves_punctuation(self) -> None:
        text = "Hello, world! How's it going?"
        result = self.cleaner.clean(text)
        assert result == text

    def test_preserves_contractions(self) -> None:
        text = "I'm gonna wanna do it"
        result = self.cleaner.clean(text)
        assert result == text

    def test_removes_song_structure_tags(self) -> None:
        text = "[Verse 1]\nI'll tell you my story\n[Chorus]\nSing along"
        result = self.cleaner.clean(text)
        assert "[Verse 1]" not in result
        assert "[Chorus]" not in result
        assert "I'll tell you my story" in result
        assert "Sing along" in result

    def test_removes_song_structure_tags_variants(self) -> None:
        text = "[Bridge]\nBreak it down\n[Outro]\nFade out\n[Pre-Chorus]\nBuilding up"
        result = self.cleaner.clean(text)
        assert "[Bridge]" not in result
        assert "[Outro]" not in result
        assert "[Pre-Chorus]" not in result

    def test_empty_input(self) -> None:
        assert self.cleaner.clean("") == ""
        assert self.cleaner.clean("   ") == ""
