"""Integration tests: real sentences through spaCy + PhrasalVerbDetector.

These sentences come from source id=2 (HIMYM) and verify that the detector
produces correct lemmas when given real spaCy parse trees (not hand-crafted
token lists).
"""

from __future__ import annotations

import pytest
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer


@pytest.fixture(scope="module")
def analyzer() -> SpaCyTextAnalyzer:
    return SpaCyTextAnalyzer()


@pytest.fixture(scope="module")
def detector() -> PhrasalVerbDetector:
    return PhrasalVerbDetector(JsonPhrasalVerbDictionary())


def _detect_lemmas(
    analyzer: SpaCyTextAnalyzer,
    detector: PhrasalVerbDetector,
    sentence: str,
) -> set[str]:
    """Run sentence through spaCy + detector, return set of detected lemmas."""
    tokens = analyzer.analyze(sentence)
    matches = detector.detect(tokens)
    return {m.lemma for m in matches}


@pytest.mark.integration
class TestHIMYMPhrasalVerbs:
    """Phrasal verbs from HIMYM source — real spaCy parse trees."""

    def test_make_fun_of(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'make fun of' — VERB+NOUN+PREP where prep is child of verb."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "made fun of me, even though it wasn't my fault",
        )
        assert "make fun of" in lemmas

    def test_get_out_of(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'get out of' — spaCy parses 'out' as prep, producing 3-word PV."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "I couldn't completely get you out of that one.",
        )
        assert "get out of" in lemmas

    def test_go_through_with(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'go through with' — prt 'through' + prep 'with' → 3-word PV."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "going through with this wedding",
        )
        assert "go through with" in lemmas

    def test_take_to(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'take to' with NP 'Robin' separating verb from prep."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "then Ted wanted to take Robin to a wedding",
        )
        assert "take to" in lemmas

    def test_go_out(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'go out' — irregular form 'went out'."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "common courtesy went out the window when I did",
        )
        assert "go out" in lemmas
