from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.services.topic_phrase_selection import (
    find_shortest_sentence,
    parse_marked_phrase,
    pick_easiest_phrase,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY, Vocabulary

from tests.phrase_support import make_occurrence, phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence

pytestmark = pytest.mark.unit


def _knowledge(vocabulary: Vocabulary = EMPTY_VOCABULARY) -> UserKnowledge:
    return UserKnowledge(vocabulary, CEFRLevel.B1, frequent_zipf=None)


def _candidate(fragment: str, new_words: tuple[str, ...] = ()) -> Occurrence:
    return replace(
        make_occurrence(), source_phrase=phrase(fragment, "negotiate", new=new_words),
    )


class TestParseMarkedPhrase:
    def test_splits_sentence_and_target(self) -> None:
        phrase = parse_marked_phrase("We agreed to **meet halfway** on the price.")
        assert phrase is not None
        assert phrase.text == "We agreed to meet halfway on the price."
        assert phrase.target == "meet halfway"

    def test_keeps_the_place_of_the_bold_occurrence(self) -> None:
        phrase = parse_marked_phrase("She runs fast, she **runs** more.")
        assert phrase is not None
        assert phrase.spans == ((19, 23),)

    def test_separated_bold_parts_are_one_target(self) -> None:
        phrase = parse_marked_phrase("  She **gave** it **up**.")
        assert phrase is not None
        assert phrase.text == "She gave it up."
        assert phrase.target == "gave up"
        assert [phrase.text[s:e] for s, e in phrase.spans] == ["gave", "up"]

    def test_returns_none_without_marked_target(self) -> None:
        assert parse_marked_phrase("We agreed to meet halfway.") is None

    def test_returns_none_for_empty_target(self) -> None:
        assert parse_marked_phrase("We agreed **  ** to it.") is None


class TestPickEasiestPhrase:
    def test_prefers_clean_phrase_over_shorter_dirty_one(self) -> None:
        dirty = _candidate("They negotiate stealthily.", new_words=("stealthily",))
        clean = _candidate("We will negotiate the price tomorrow.")
        assert pick_easiest_phrase([dirty, clean], _knowledge()) is clean

    def test_word_the_user_knows_does_not_make_phrase_dirty(self) -> None:
        known = _candidate("They negotiate stealthily.", new_words=("stealthily",))
        longer = _candidate("We will negotiate the price tomorrow.")
        vocabulary = Vocabulary.of(known={"stealthily"}, unknown=set())
        assert pick_easiest_phrase([known, longer], _knowledge(vocabulary)) is known

    def test_prefers_shorter_phrase_among_clean_ones(self) -> None:
        long = _candidate("We will negotiate the price with them tomorrow morning.")
        short = _candidate("We will negotiate the price.")
        assert pick_easiest_phrase([long, short], _knowledge()) is short

    def test_returns_none_for_no_candidates(self) -> None:
        assert pick_easiest_phrase([], _knowledge()) is None


class TestFindShortestSentence:
    TEXT = (
        "It was a long day. In the end we agreed to meet halfway on almost everything "
        "they asked for that week. They Met Halfway on the price.\n"
        "Nobody wanted to meet."
    )

    def test_finds_shortest_sentence_with_any_variant(self) -> None:
        found = find_shortest_sentence(self.TEXT, {"meet halfway", "met halfway"})
        assert found is not None
        assert found.text == "They Met Halfway on the price."
        assert found.target == "Met Halfway"

    def test_matches_whole_words_only(self) -> None:
        assert find_shortest_sentence("A meeting was planned for the team.", {"meet"}) is None

    def test_matches_across_extra_whitespace(self) -> None:
        found = find_shortest_sentence("They will meet\thalfway on it soon.", {"meet halfway"})
        assert found is not None
        assert found.text == "They will meet halfway on it soon."

    def test_skips_sentences_that_are_too_short(self) -> None:
        assert find_shortest_sentence("Meet halfway.", {"meet halfway"}) is None

    def test_returns_none_without_variants(self) -> None:
        assert find_shortest_sentence(self.TEXT, {" "}) is None
