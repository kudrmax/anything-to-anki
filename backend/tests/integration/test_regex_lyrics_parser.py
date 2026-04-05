import pytest
from backend.infrastructure.adapters.regex_lyrics_parser import RegexLyricsParser
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer


@pytest.mark.integration
class TestRegexLyricsParser:
    def setup_method(self) -> None:
        self.parser = RegexLyricsParser(SpaCyTextAnalyzer())

    def test_lyrics_adds_period_to_bare_lines(self) -> None:
        text = "I'll tell you my story\nDon't call me typical\nInto a genius."
        result = self.parser.parse(text)
        lines = result.splitlines()
        assert lines[0] == "I'll tell you my story."
        # "Don't call me typical" is followed by "Into a genius." which starts with a
        # preposition — spaCy sees it as a continuation, so no period is added here.
        assert lines[2] == "Into a genius."

    def test_lyrics_does_not_duplicate_existing_punctuation(self) -> None:
        text = "What's going on?\nI don't know!\nHello world"
        result = self.parser.parse(text)
        assert "?." not in result
        assert "!." not in result
        assert "world." in result

    def test_lyrics_enjambment_tier1_no_period_on_preposition(self) -> None:
        # Line ends with preposition (ADP) — Tier 1 catches it, no period
        text = "She was lost in\nthe shadows of night"
        result = self.parser.parse(text)
        assert "in." not in result

    def test_lyrics_enjambment_tier2_no_period_on_verb_with_object_on_next_line(self) -> None:
        # Verb's object is on the next line — Tier 2 catches it, no period
        text = "then I get\ntheir Mortys torture"
        result = self.parser.parse(text)
        assert "get." not in result

    # --- Independent sentences: period must be added ---

    def test_lyrics_independent_sentences_sing_guitar(self) -> None:
        text = "She loves to sing\nHe plays guitar"
        result = self.parser.parse(text)
        assert result.splitlines()[0].endswith(".")

    def test_lyrics_independent_sentences_run_fly(self) -> None:
        text = "I was born to run\nShe was made to fly"
        result = self.parser.parse(text)
        assert result.splitlines()[0].endswith(".")

    def test_lyrics_independent_sentences_alive_nothing(self) -> None:
        text = "You make me feel alive\nNothing could stop us now"
        result = self.parser.parse(text)
        assert result.splitlines()[0].endswith(".")

    # --- Enjambment: period must NOT be added ---

    def test_lyrics_enjambment_adv_then_prep(self) -> None:
        # "right" ends line, next line starts with preposition "through"
        text = "She walked right\nthrough the door"
        result = self.parser.parse(text)
        assert "right." not in result

    def test_lyrics_enjambment_verb_then_acomp(self) -> None:
        # "getting" ends line, next line is adjective complement
        text = "He was getting\ncloser and closer"
        result = self.parser.parse(text)
        assert "getting." not in result

    def test_lyrics_enjambment_adv_then_acomp(self) -> None:
        # "so" ends line, next line is adjective complement
        text = "She was so\nbeautiful tonight"
        result = self.parser.parse(text)
        assert "so." not in result

    def test_lyrics_enjambment_pron_then_pobj(self) -> None:
        # "her" ends line, next line is the object of the preposition
        text = "She's got me wrapped around her\nLittle finger"
        result = self.parser.parse(text)
        assert "her." not in result

    def test_lyrics_enjambment_adj_then_prep(self) -> None:
        # "bright" ends line, next line is prepositional phrase
        text = "The sun was shining bright\non the water below"
        result = self.parser.parse(text)
        assert "bright." not in result

    def test_lyrics_enjambment_adv_then_attr(self) -> None:
        # "always" ends line, next line is the predicate
        text = "She was always\nthe brightest in the room"
        result = self.parser.parse(text)
        assert "always." not in result

    def test_lyrics_enjambment_aux_ending(self) -> None:
        # "could" is AUX — Tier 1 catches it, no period
        text = "Nothing in this world could\nmake me leave"
        result = self.parser.parse(text)
        assert "could." not in result
