from __future__ import annotations

import pytest
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer


@pytest.mark.integration
class TestSlangNormalizationPipeline:
    """End-to-end: normalize slang → spaCy analysis → verify correct lemma/POS."""

    def setup_method(self) -> None:
        self.normalizer = SlangNormalizer()
        self.analyzer = SpaCyTextAnalyzer()

    def test_wanna_produces_correct_lemma_and_pos(self) -> None:
        normalized = self.normalizer.normalize("I wanna buy something")
        assert normalized == "I want to buy something"
        tokens = self.analyzer.analyze(normalized)
        want_tokens = [t for t in tokens if t.text == "want"]
        assert len(want_tokens) == 1
        assert want_tokens[0].lemma == "want"
        assert want_tokens[0].pos == "VERB"

    def test_tryna_produces_correct_lemma_and_pos(self) -> None:
        normalized = self.normalizer.normalize("He's tryna help")
        assert normalized == "He's trying to help"
        tokens = self.analyzer.analyze(normalized)
        trying_tokens = [t for t in tokens if t.text == "trying"]
        assert len(trying_tokens) == 1
        assert trying_tokens[0].lemma == "try"
        assert trying_tokens[0].pos == "VERB"

    def test_dunno_produces_correct_lemma_and_pos(self) -> None:
        normalized = self.normalizer.normalize("I dunno what happened")
        assert normalized == "I do not know what happened"
        tokens = self.analyzer.analyze(normalized)
        know_tokens = [t for t in tokens if t.text == "know"]
        assert len(know_tokens) == 1
        assert know_tokens[0].lemma == "know"
        assert know_tokens[0].pos == "VERB"

    def test_yall_produces_correct_pos(self) -> None:
        normalized = self.normalizer.normalize("Y'all should come")
        assert normalized == "You all should come"
        tokens = self.analyzer.analyze(normalized)
        you_tokens = [t for t in tokens if t.text.lower() == "you"]
        assert len(you_tokens) == 1
        assert you_tokens[0].pos == "PRON"

    def test_dropped_g_produces_correct_lemma(self) -> None:
        normalized = self.normalizer.normalize("She's runnin' fast")
        assert normalized == "She's running fast"
        tokens = self.analyzer.analyze(normalized)
        running_tokens = [t for t in tokens if t.text == "running"]
        assert len(running_tokens) == 1
        assert running_tokens[0].lemma == "run"
        assert running_tokens[0].pos == "VERB"

    def test_lemme_produces_correct_parse(self) -> None:
        normalized = self.normalizer.normalize("Lemme see that")
        assert normalized == "Let me see that"
        tokens = self.analyzer.analyze(normalized)
        let_tokens = [t for t in tokens if t.text.lower() == "let"]
        assert len(let_tokens) == 1
        assert let_tokens[0].lemma == "let"
        assert let_tokens[0].pos == "VERB"

    def test_coulda_produces_correct_parse(self) -> None:
        normalized = self.normalizer.normalize("I coulda done it")
        assert normalized == "I could have done it"
        tokens = self.analyzer.analyze(normalized)
        could_tokens = [t for t in tokens if t.text == "could"]
        assert len(could_tokens) == 1
        assert could_tokens[0].pos in ("AUX", "VERB")
