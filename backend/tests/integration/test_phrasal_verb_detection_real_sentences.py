"""Integration tests: real sentences through spaCy + PhrasalVerbDetector.

Real sentences → spaCy parse → PhrasalVerbDetector → check detected lemmas.
Tests verify that the detector handles real spaCy parse trees correctly,
including edge cases like separated particles, passives, relative clauses,
and three-word phrasal verbs.
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


@pytest.mark.integration
class TestEdgeCasePhrasalVerbs:
    """Edge-case phrasal verbs targeting weak spots in the detector."""

    # --- Separated particles ---

    def test_pick_up_separated_by_dobj(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'pick up' — particle separated from verb by dobj 'the kids'."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "She finally picked the kids up from soccer practice.",
        )
        assert "pick up" in lemmas

    def test_figure_out_with_pronoun(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'figure out' — pronoun 'it' between verb and particle."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "Just figure it out already.",
        )
        assert "figure out" in lemmas

    # --- Three-word phrasal verbs ---

    def test_put_up_with(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'put up with' — canonical 3-word PV, prt+prep."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "I can't put up with this anymore.",
        )
        assert "put up with" in lemmas

    def test_come_up_with(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'come up with' — 3-word PV, 'up' may be advmod instead of prt."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "She came up with a brilliant idea during lunch.",
        )
        assert "come up with" in lemmas

    def test_come_up_with_in_cleft(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'come up with' — inside cleft + infinitive chain, verb deeply nested."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "That's what I was trying to come up with earlier.",
        )
        assert "come up with" in lemmas

    def test_cut_down_on(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'cut down on' — prt+prep, spaCy may chain as prep→prep."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "We need to cut down on sugar this month.",
        )
        assert "cut down on" in lemmas

    def test_get_away_with(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'get away with' — 'away' often parsed as advmod, not prt."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "Don't let him get away with that.",
        )
        assert "get away with" in lemmas

    # --- Interrogative / fronted forms ---

    def test_end_up_in_question(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'end up' — interrogative form, 'up' may get advmod."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "What did you end up doing last night?",
        )
        assert "end up" in lemmas

    def test_take_after_in_question(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'take after' — question with fronted 'who', stranded prep."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "Who do you take after, your mom or your dad?",
        )
        assert "take after" in lemmas

    # --- Passive constructions ---

    def test_make_fun_of_passive(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'make fun of' — passive, 'fun' may shift from dobj."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "He was made fun of by everyone in the class.",
        )
        assert "make fun of" in lemmas

    def test_put_off_passive_with_got(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'put off' — passive via 'got', main verb may be parsed as xcomp."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "The meeting got put off until next Tuesday.",
        )
        assert "put off" in lemmas

    # --- Relative clauses / stranded prepositions ---

    def test_look_forward_to_relative_clause(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'look forward to' — relative clause, stranded 'to', 'forward' as advmod."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "It's something I've always looked forward to.",
        )
        assert "look forward to" in lemmas

    def test_look_up_to_relative_clause(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'look up to' — relative clause without that/who, stranded 'to'."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "The person I look up to the most is my grandmother.",
        )
        assert "look up to" in lemmas

    # --- VERB+NOUN+PREP idioms ---

    def test_get_rid_of(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'get rid of' — 'rid' is ADJ not NOUN, breaks Layer 3 pattern."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "I need to get rid of these old boxes.",
        )
        assert "get rid of" in lemmas

    def test_keep_track_of(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'keep track of' — VERB+NOUN+PREP, 'of' attachment varies."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "Make sure to keep track of your receipts.",
        )
        assert "keep track of" in lemmas

    def test_pay_attention_to(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'pay attention to' — 'more' intervenes, 'to' attachment varies."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "You really need to pay more attention to the details.",
        )
        assert "pay attention to" in lemmas

    # --- Simple verb+prep ---

    def test_get_over(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'get over' — prep with gerund pobj, prt/prep ambiguity."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "He just couldn't get over her leaving.",
        )
        assert "get over" in lemmas

    # --- Not in dictionary (expect failure) ---

    def test_tell_about_not_in_dictionary(
        self, analyzer: SpaCyTextAnalyzer, detector: PhrasalVerbDetector
    ) -> None:
        """'tell about' — not in PV dictionary, should NOT be detected."""
        lemmas = _detect_lemmas(
            analyzer, detector,
            "That's the guy I was telling you about.",
        )
        assert "tell about" not in lemmas
