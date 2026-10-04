from __future__ import annotations

import pytest
from backend.domain.services.phrase_target import normalize_target, phrase_contains_target

pytestmark = pytest.mark.unit


def test_punctuation_picked_with_a_word_is_dropped() -> None:
    assert normalize_target("“procrastinate,”") == "procrastinate"


def test_target_word_found_regardless_of_case_and_punctuation() -> None:
    assert phrase_contains_target("Stop procrastinating, Max!", "PROCRASTINATING")


def test_separated_phrasal_verb_counts_as_contained() -> None:
    assert phrase_contains_target("Don't give it up now", "give up")


def test_word_missing_from_phrase_is_rejected() -> None:
    assert not phrase_contains_target("Don't give it up now", "give in")


def test_part_of_a_word_is_rejected() -> None:
    assert not phrase_contains_target("procrastinating again", "procrastinate")


def test_empty_target_is_rejected() -> None:
    assert not phrase_contains_target("Anything at all", " , ")
