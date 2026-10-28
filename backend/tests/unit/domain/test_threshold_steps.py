from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.services.candidate_sections import card_section, sections_by_step
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import (
    FREQUENT_WORD_THRESHOLDS,
    THRESHOLD_STEPS,
    FrequentWordThreshold,
    step_index,
)
from backend.domain.value_objects.phrase import Word
from backend.domain.value_objects.phrase_newness import PhraseNewness
from backend.domain.value_objects.user_knowledge import (
    KnowledgeBase,
    Newness,
    UserKnowledge,
    newness,
)
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY, Vocabulary

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

pytestmark = pytest.mark.unit

ZIPF_STEPS = [step for step in THRESHOLD_STEPS if step is not None]


class TestSteps:
    def test_every_step_has_its_own_index(self) -> None:
        assert [step_index(step) for step in THRESHOLD_STEPS] == list(range(len(THRESHOLD_STEPS)))

    def test_no_threshold_is_the_last_step(self) -> None:
        assert step_index(None) == len(THRESHOLD_STEPS) - 1

    @pytest.mark.parametrize("zipf", [4.2, 2.0, 6.0])
    def test_a_value_between_or_beyond_the_steps_is_refused(self, zipf: float) -> None:
        with pytest.raises(ValueError, match="Not a threshold step"):
            step_index(zipf)

    def test_every_option_is_a_step(self) -> None:
        for threshold in FREQUENT_WORD_THRESHOLDS:
            step_index(threshold.zipf)



def _word(lemma: str, level: CEFRLevel, zipf: float, *, content: bool) -> Word:
    return Word(start=0, end=1, lemma=lemma, level=level, zipf=zipf, content=content)


VOCABULARIES = {
    "empty": EMPTY_VOCABULARY,
    "known": Vocabulary.of(known={"gull"}, unknown=set()),
    "unknown": Vocabulary.of(known=set(), unknown={"gull"}),
    "learning": Vocabulary.of(known=set(), unknown=set(), learning={"gull"}),
}


class TestNewness:
    def test_unknown_and_learning_are_always_new(self) -> None:
        word = _word("gull", CEFRLevel.A1, 7.0, content=False)
        assert newness(word, VOCABULARIES["unknown"], CEFRLevel.B1) is Newness.ALWAYS
        assert newness(word, VOCABULARIES["learning"], CEFRLevel.B1) is Newness.ALWAYS

    def test_known_and_function_words_are_never_new(self) -> None:
        rare = _word("gull", CEFRLevel.C2, 2.0, content=True)
        assert newness(rare, VOCABULARIES["known"], CEFRLevel.B1) is Newness.NEVER
        function = _word("gull", CEFRLevel.C2, 2.0, content=False)
        assert newness(function, EMPTY_VOCABULARY, CEFRLevel.B1) is Newness.NEVER

    def test_a_word_of_the_level_or_harder_is_new_if_rare(self) -> None:
        word = _word("gull", CEFRLevel.C1, 3.0, content=True)
        assert newness(word, EMPTY_VOCABULARY, CEFRLevel.B1) is Newness.IF_RARE
        assert newness(word, EMPTY_VOCABULARY, CEFRLevel.C1) is Newness.IF_RARE
        assert newness(word, EMPTY_VOCABULARY, CEFRLevel.C2) is Newness.NEVER

    def test_newness_agrees_with_is_new_everywhere(self) -> None:
        cases = itertools.product(
            VOCABULARIES.values(), CEFRLevel, CEFRLevel, [2.0, 3.0, 4.5, 6.0], [True, False],
            THRESHOLD_STEPS,
        )
        for vocabulary, user_level, word_level, zipf, content, step in cases:
            word = _word("gull", word_level, zipf, content=content)
            knowledge = UserKnowledge(vocabulary, user_level, step)
            word_newness = KnowledgeBase(vocabulary, user_level).newness(word)
            expected = {
                Newness.ALWAYS: True,
                Newness.IF_RARE: step is None or zipf < step,
                Newness.NEVER: False,
            }[word_newness]
            assert knowledge.is_new(word) is expected


class TestPhraseNewness:
    def test_a_lemma_counts_once(self) -> None:
        words = PhraseNewness.of([("grim", 3.0, Newness.ALWAYS), ("grim", 3.0, Newness.ALWAYS)])
        assert words.count(None) == 1

    def test_a_rare_word_is_new_only_below_the_step(self) -> None:
        words = PhraseNewness.of([("grim", 4.0, Newness.IF_RARE)])
        assert words.count(4.5) == 1
        assert words.count(4.0) == 0
        assert words.count(3.5) == 0
        assert words.count(None) == 1

    def test_newness_classes_at_a_step(self) -> None:
        words = PhraseNewness.of([
            ("always", 6.0, Newness.ALWAYS),
            ("rare", 3.0, Newness.IF_RARE),
            ("common", 5.0, Newness.IF_RARE),
            ("never", 2.0, Newness.NEVER),
        ])
        assert words.new_lemmas(4.0) == ["always", "rare"]
        assert words.count(None) == 3

    def test_a_lemma_new_in_one_place_counts(self) -> None:
        words = PhraseNewness.of([("grim", 5.0, Newness.IF_RARE), ("grim", 3.0, Newness.IF_RARE)])
        assert words.new_lemmas(4.0) == ["grim"]


@dataclass(frozen=True)
class _Card:
    lemma: str
    pos: str
    zipf_frequency: float
    phrase: Phrase
    is_done: bool
    earned_section: CandidateSection


def _with_zipfs(shown: Phrase, zipfs: dict[str, float]) -> Phrase:
    words = tuple(replace(w, zipf=zipfs.get(w.lemma, w.zipf)) for w in shown.words)
    return replace(shown, words=words)


PHRASES = [
    phrase("the scythe", "scythe"),
    phrase("the scythe gleams", "scythe", new=["gleams"]),
    _with_zipfs(phrase("grim grim scythe", "scythe", new=["grim"]), {"grim": 3.0}),
    _with_zipfs(phrase("a dim quill scythe", "scythe", new=["dim", "quill"]),
                {"dim": 4.0, "quill": 5.5}),
    phrase("context for gull scythe", "scythe"),
]
TARGETS = [("scythe", "NOUN", zipf) for zipf in (0.0, 2.4, 3.0, 4.0, 4.7, 5.5, 6.5)] + [
    ("oh", "INTJ", 5.0),
]
VOCABULARIES_OF_PHRASES = [
    EMPTY_VOCABULARY,
    Vocabulary.of(known={"gleams", "dim"}, unknown=set()),
    Vocabulary.of(known=set(), unknown={"context"}),
    Vocabulary.of(known=set(), unknown=set(), learning={"for", "quill"}),
]


def test_sections_by_step_agree_with_card_section_at_every_step() -> None:
    cases = itertools.product(
        PHRASES, TARGETS, [False, True], list(CandidateSection), VOCABULARIES_OF_PHRASES,
        [CEFRLevel.B1, CEFRLevel.C2],
    )
    for shown, (lemma, pos, zipf), done, earned, vocabulary, level in cases:
        card = _Card(lemma, pos, zipf, shown, done, earned)
        by_step = sections_by_step(card, KnowledgeBase(vocabulary, level))
        assert len(by_step) == len(THRESHOLD_STEPS)
        for step in THRESHOLD_STEPS:
            threshold = FrequentWordThreshold("step", step, ())
            expected = card_section(card, UserKnowledge(vocabulary, level, step), threshold)
            assert by_step[step_index(step)] is expected


def test_without_knowledge_no_other_word_is_new() -> None:
    card = _Card("scythe", "NOUN", 2.0, PHRASES[1], False, CandidateSection.READY)
    assert sections_by_step(card, None) == (CandidateSection.READY,) * len(THRESHOLD_STEPS)
    assert card_section(card, None, None) is CandidateSection.READY
