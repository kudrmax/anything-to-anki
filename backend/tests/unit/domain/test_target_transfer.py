"""The target of a rewritten phrase, found among the words of the phrase it was cut as."""
from __future__ import annotations

from backend.domain.services.target_transfer import target_in

from tests.phrase_support import phrase

SOURCE = phrase("She gave the old plan up at last.")


def test_the_same_text_keeps_the_target_as_it_is() -> None:
    shown = SOURCE.with_target((1, 5))

    assert target_in(SOURCE, shown) == (1, 5)


def test_a_rewrite_finds_the_target_by_dictionary_form_in_order() -> None:
    shown = phrase("At last she gave up the plan.").with_target((3, 4))

    assert target_in(SOURCE, shown) == (1, 5)


def test_a_word_the_source_lacks_finds_nothing() -> None:
    shown = phrase("She gave the new plan up.").with_target((3,))

    assert target_in(SOURCE, shown) is None


def test_words_out_of_the_source_order_find_nothing() -> None:
    shown = phrase("Up she gave it.").with_target((0, 2))

    assert target_in(SOURCE, shown) is None
