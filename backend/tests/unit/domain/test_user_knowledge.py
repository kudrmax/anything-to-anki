from __future__ import annotations

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Word
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY, Vocabulary

pytestmark = pytest.mark.unit


def _word(
    lemma: str, level: CEFRLevel = CEFRLevel.C1, zipf: float = 3.0, *, content: bool = True,
) -> Word:
    return Word(start=0, end=1, lemma=lemma, level=level, zipf=zipf, content=content)


def _knowledge(
    vocabulary: Vocabulary = EMPTY_VOCABULARY,
    level: CEFRLevel = CEFRLevel.B1,
    frequent: float | None = 4.5,
) -> UserKnowledge:
    return UserKnowledge(vocabulary=vocabulary, user_level=level, frequent_zipf=frequent)


class TestIsNew:
    def test_rare_word_above_the_level_is_new(self) -> None:
        assert _knowledge().is_new(_word("gull")) is True

    def test_known_word_is_not_new(self) -> None:
        known = Vocabulary.of(known={"gull"}, unknown=set())
        assert _knowledge(known).is_new(_word("gull")) is False

    def test_word_at_the_users_level_is_not_new(self) -> None:
        assert _knowledge(level=CEFRLevel.C1).is_new(_word("gull")) is False

    def test_frequent_word_is_not_new(self) -> None:
        assert _knowledge().is_new(_word("gull", zipf=5.0)) is False

    def test_frequency_is_ignored_when_the_threshold_is_off(self) -> None:
        assert _knowledge(frequent=None).is_new(_word("gull", zipf=5.0)) is True

    def test_function_word_is_never_new_by_itself(self) -> None:
        assert _knowledge().is_new(_word("the", content=False)) is False

    def test_word_the_user_marked_unknown_is_new_whatever_it_is(self) -> None:
        unknown = Vocabulary.of(known=set(), unknown={"the"})
        assert _knowledge(unknown).is_new(_word("the", CEFRLevel.A1, 7.0, content=False)) is True


class TestLearning:
    """Priority: Unknown > Known > learning ("учу")."""

    def test_a_learning_word_is_new_and_not_known(self) -> None:
        learning = Vocabulary.of(known=set(), unknown=set(), learning={"gull"})
        assert learning.is_learning("gull") is True
        assert learning.is_known("gull") is False
        assert _knowledge(learning).is_new(_word("gull", CEFRLevel.A1, 7.0)) is True

    def test_known_is_stronger_than_learning(self) -> None:
        both = Vocabulary.of(known={"gull"}, unknown=set(), learning={"gull"})
        assert both.is_known("gull") is True
        assert both.is_learning("gull") is False
        assert _knowledge(both).is_new(_word("gull")) is False

    def test_unknown_is_stronger_than_learning(self) -> None:
        both = Vocabulary.of(known=set(), unknown={"gull"}, learning={"gull"})
        assert both.is_unknown("gull") is True
        assert both.is_learning("gull") is False

    def test_known_or_learning_is_no_new_candidate(self) -> None:
        vocabulary = Vocabulary.of(known={"gull"}, unknown=set(), learning={"Tern"})
        assert vocabulary.is_known_or_learning("gull") is True
        assert vocabulary.is_known_or_learning("tern") is True
        assert vocabulary.is_known_or_learning("puffin") is False

    def test_without_learning_drops_only_the_given_lemmas(self) -> None:
        vocabulary = Vocabulary.of(known=set(), unknown=set(), learning={"gull", "tern"})
        assert vocabulary.without_learning({"Gull"}).learning == frozenset({"tern"})
