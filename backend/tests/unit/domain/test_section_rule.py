from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import SectionRule, section_of
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY

from tests.phrase_support import EASY_ZIPF, RARE_ZIPF, phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

NORMAL_POS = "NOUN"
FREQUENT_ZIPF = 5.0
THRESHOLD = FrequentWordThreshold.from_key("4.0")
KNOWLEDGE = UserKnowledge(EMPTY_VOCABULARY, CEFRLevel.B1, THRESHOLD.zipf)


@dataclass(frozen=True)
class _Facts:
    lemma: str
    pos: str = NORMAL_POS
    zipf_frequency: float = RARE_ZIPF


@dataclass(frozen=True)
class _Card:
    lemma: str
    pos: str
    zipf_frequency: float
    phrase: Phrase


def _rule(threshold: FrequentWordThreshold | None = None) -> SectionRule:
    return SectionRule(knowledge=KNOWLEDGE, frequent_threshold=threshold)


def test_only_the_target_new_earns_ready() -> None:
    shown = phrase("a zephyr", "zephyr", new=("zephyr",))
    assert _rule().earned(shown, _Facts("zephyr")) is CandidateSection.READY


def test_another_new_word_earns_extra() -> None:
    shown = phrase("a zephyr quill", "zephyr", new=("zephyr", "quill"))
    assert _rule().earned(shown, _Facts("zephyr")) is CandidateSection.EXTRA


def test_a_frequent_target_earns_probably_known() -> None:
    shown = phrase("a zephyr", "zephyr")
    earned = _rule(THRESHOLD).earned(shown, _Facts("zephyr", zipf_frequency=FREQUENT_ZIPF))
    assert earned is CandidateSection.PROBABLY_KNOWN


def test_an_interjection_earns_probably_known() -> None:
    shown = phrase("oh well", "oh")
    assert _rule().earned(shown, _Facts("oh", pos="INTJ")) is CandidateSection.PROBABLY_KNOWN


def test_the_rule_agrees_with_section_of() -> None:
    cases = [
        (phrase("a zephyr", "zephyr", new=("zephyr",)), _Facts("zephyr"), None),
        (phrase("a zephyr quill", "zephyr", new=("zephyr", "quill")), _Facts("zephyr"), None),
        (phrase("a zephyr", "zephyr"), _Facts("zephyr", zipf_frequency=FREQUENT_ZIPF), THRESHOLD),
        (phrase("oh well", "oh"), _Facts("oh", pos="INTJ", zipf_frequency=EASY_ZIPF), None),
    ]
    for shown, word, threshold in cases:
        card = _Card(word.lemma, word.pos, word.zipf_frequency, shown)
        expected = section_of(card, KNOWLEDGE, threshold)
        assert _rule(threshold).earned(shown, word) is expected
