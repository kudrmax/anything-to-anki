import pytest
from backend.domain.value_objects.source_type import SourceType
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer


@pytest.mark.integration
class TestRegexTextCleaner:
    def setup_method(self) -> None:
        self.cleaner = RegexTextCleaner(SpaCyTextAnalyzer())

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

    def test_lyrics_adds_period_to_bare_lines(self) -> None:
        text = "I'll tell you my story\nDon't call me typical\nInto a genius."
        result = self.cleaner.clean(text, SourceType.LYRICS)
        lines = result.splitlines()
        assert lines[0] == "I'll tell you my story."
        # "Don't call me typical" is followed by "Into a genius." which starts with a
        # preposition — spaCy sees it as a continuation, so no period is added here.
        assert lines[2] == "Into a genius."

    def test_text_type_does_not_add_periods(self) -> None:
        text = "I'll tell you my story\nDon't call me typical"
        result = self.cleaner.clean(text, SourceType.TEXT)
        assert "story." not in result
        assert "typical." not in result

    def test_lyrics_does_not_duplicate_existing_punctuation(self) -> None:
        text = "What's going on?\nI don't know!\nHello world"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "?." not in result
        assert "!." not in result
        assert "world." in result

    def test_lyrics_enjambment_tier1_no_period_on_preposition(self) -> None:
        # Line ends with preposition (ADP) — Tier 1 catches it, no period
        text = "She was lost in\nthe shadows of night"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "in." not in result

    def test_lyrics_enjambment_tier2_no_period_on_verb_with_object_on_next_line(self) -> None:
        # Verb's object is on the next line — Tier 2 catches it, no period
        text = "then I get\ntheir Mortys torture"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "get." not in result

    # --- Independent sentences: period must be added ---

    def test_lyrics_independent_sentences_sing_guitar(self) -> None:
        text = "She loves to sing\nHe plays guitar"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert result.splitlines()[0].endswith(".")

    def test_lyrics_independent_sentences_run_fly(self) -> None:
        text = "I was born to run\nShe was made to fly"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert result.splitlines()[0].endswith(".")

    def test_lyrics_independent_sentences_alive_nothing(self) -> None:
        text = "You make me feel alive\nNothing could stop us now"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert result.splitlines()[0].endswith(".")

    # --- Enjambment: period must NOT be added ---

    def test_lyrics_enjambment_adv_then_prep(self) -> None:
        # "right" ends line, next line starts with preposition "through"
        text = "She walked right\nthrough the door"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "right." not in result

    def test_lyrics_enjambment_verb_then_acomp(self) -> None:
        # "getting" ends line, next line is adjective complement
        text = "He was getting\ncloser and closer"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "getting." not in result

    def test_lyrics_enjambment_adv_then_acomp(self) -> None:
        # "so" ends line, next line is adjective complement
        text = "She was so\nbeautiful tonight"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "so." not in result

    def test_lyrics_enjambment_pron_then_pobj(self) -> None:
        # "her" ends line, next line is the object of the preposition
        text = "She's got me wrapped around her\nLittle finger"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "her." not in result

    def test_lyrics_enjambment_adj_then_prep(self) -> None:
        # "bright" ends line, next line is prepositional phrase
        text = "The sun was shining bright\non the water below"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "bright." not in result

    def test_lyrics_enjambment_adv_then_attr(self) -> None:
        # "always" ends line, next line is the predicate
        text = "She was always\nthe brightest in the room"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "always." not in result

    def test_lyrics_enjambment_aux_ending(self) -> None:
        # "could" is AUX — Tier 1 catches it, no period
        text = "Nothing in this world could\nmake me leave"
        result = self.cleaner.clean(text, SourceType.LYRICS)
        assert "could." not in result
