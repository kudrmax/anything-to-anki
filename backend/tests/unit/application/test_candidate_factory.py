"""CandidateFactory: several words picked together stay one target."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.utils.candidate_factory import CandidateFactory
from backend.domain.entities.token_data import TokenData
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase_origin import PhraseOrigin

pytestmark = pytest.mark.unit


def _token(
    index: int, text: str, lemma: str, *, pos: str = "NOUN", punct: bool = False, ws: str = " ",
) -> TokenData:
    return TokenData(
        index=index, text=text, lemma=lemma, pos="PUNCT" if punct else pos, tag="NN",
        head_index=0, children_indices=(), is_punct=punct, is_stop=False,
        is_alpha=not punct, is_propn=False, sent_index=0, whitespace_after=ws,
    )


def _factory(analyses: list[list[TokenData]]) -> CandidateFactory:
    analyzer = MagicMock()
    analyzer.analyze.side_effect = analyses
    classifier = MagicMock()
    classifier.classify_detailed.return_value = CEFRBreakdown(
        final_level=CEFRLevel.UNKNOWN, decision_method="voting", priority_votes=[], votes=[],
    )
    frequency = MagicMock()
    frequency.get_zipf_value.return_value = 2.5
    detector = MagicMock()
    detector.detect.return_value = []
    return CandidateFactory(analyzer, classifier, frequency, detector)


def test_collocation_lemma_is_lemmatised_phrase() -> None:
    context = [_token(0, "We", "we"), _token(1, "made", "make", pos="VERB"), _token(2, "a", "a"),
               _token(3, "decision", "decision", ws="")]
    surface = [
        _token(0, "made", "make", pos="VERB"), _token(1, "a", "a"),
        _token(2, "decision", "decision", ws=""),
    ]
    candidate = _factory([context, surface]).build(
        source_id=1, surface_form="made a decision", context_fragment="We made a decision",
        occurrences=1, origin=PhraseOrigin.generated(),
    )
    assert candidate.lemma == "make a decision"
    assert candidate.surface_form == "made a decision"
    assert candidate.is_phrasal_verb is False
    assert candidate.cefr_level is None
    assert candidate.origin == PhraseOrigin.generated()


def test_noun_phrase_keeps_its_words() -> None:
    surface = [
        _token(0, "starting", "start", pos="ADJ"),
        _token(1, "salaries", "salary", ws=""),
    ]
    candidate = _factory([surface, surface]).build(
        source_id=1, surface_form="starting salaries", context_fragment="starting salaries",
        occurrences=1,
    )
    assert candidate.lemma == "starting salaries"


def test_hyphenated_word_is_one_target() -> None:
    surface = [_token(0, "counter", "counter", ws=""), _token(1, "-", "-", punct=True, ws=""),
               _token(2, "offer", "offer", ws="")]
    candidate = _factory([surface, surface]).build(
        source_id=1, surface_form="counter-offer", context_fragment="counter-offer",
        occurrences=1,
    )
    assert candidate.lemma == "counter-offer"
