"""New cards placed into an open review's held order from the rows of their own words and
of the words a binary search compares against, without the whole set: the same order as
`place_new` gives from the whole set sorted afresh, in every sort order and at every
threshold step, sections included."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_ordering import ReviewOrdering
from backend.domain.services.candidate_sorting import sort_cards, stored_standing
from backend.domain.services.review_layout import place_new
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS
from backend.domain.value_objects.ordered_card import OrderedCard
from backend.domain.value_objects.review_order import ReviewOrder
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.projection_support import LiveSectionTallies

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from hypothesis.strategies import DrawFn

pytestmark = pytest.mark.unit

SOURCES = (1, 2, 3)
USAGE_ORDER = ["neutral", "informal"]
STEPS = len(THRESHOLD_STEPS)


class _Rows(LiveSectionTallies):
    """The stored rows of a set of cards, as the review order reads them."""

    def __init__(self, cards: Sequence[OrderedCard]) -> None:
        self._all = list(cards)
        self.words_read: set[int] = set()

    def order_rows(self, source_ids: Sequence[int]) -> list[OrderedCard]:
        raise AssertionError("placing new cards must not read the whole set")

    def order_rows_of_words(self, word_ids: Collection[int]) -> list[OrderedCard]:
        self.words_read.update(word_ids)
        return [card for card in self._all if card.word_id in word_ids]


@st.composite
def _cards(draw: DrawFn) -> list[OrderedCard]:
    cards: list[OrderedCard] = []
    phrase_id = 0
    for word_id in range(1, draw(st.integers(1, 12)) + 1):
        source_id = draw(st.sampled_from(SOURCES))
        word = {
            "word_id": word_id, "source_id": source_id, "lemma": f"w{word_id}",
            "pos": draw(st.sampled_from(["NOUN", "VERB", "INTJ"])),
            "zipf_frequency": draw(st.sampled_from([0.0, 2.0, 3.2, 4.1, 5.0, 6.0])),
            "cefr_level": draw(st.sampled_from([None, "A1", "B2", "C1"])),
            "occurrences": draw(st.integers(1, 4)),
            "is_phrasal_verb": draw(st.booleans()),
            "usage_distribution": None,
        }
        for _ in range(draw(st.integers(1, 4))):
            phrase_id += 1
            cards.append(OrderedCard(
                phrase_id=phrase_id,
                place=draw(st.none() | st.tuples(
                    st.integers(0, 3), st.integers(0, 1), st.integers(0, 9),
                )),
                is_done=draw(st.booleans()),
                sections=SectionsByStep(tuple(draw(st.lists(
                    st.sampled_from(list(CandidateSection)), min_size=STEPS, max_size=STEPS,
                )))),
                new_counts=NewCountsByStep(tuple(draw(st.lists(
                    st.integers(0, 3), min_size=STEPS, max_size=STEPS,
                )))),
                **word,  # type: ignore[arg-type]
            ))
    return cards


def _ordering(rows: _Rows, step: float | None) -> ReviewOrdering:
    threshold = MagicMock()
    threshold.resolve.return_value.zipf = step
    sorter = MagicMock()
    sorter.usage_order.return_value = USAGE_ORDER
    return ReviewOrdering(rows, threshold, sorter)


def _opened(
    cards: list[OrderedCard], sort: CandidateSortOrder, step: float | None,
) -> ReviewOrder:
    """The order a review opened on these cards holds."""
    return ReviewOrder(
        ReviewOrdering.held(sort_cards(
            cards, sort, stored_standing(step), usage_order=USAGE_ORDER, source_order=SOURCES,
        ), step),
        sectioned=sort != CandidateSortOrder.CHRONOLOGICAL,
    )


@settings(max_examples=200, deadline=None)
@given(
    cards=_cards(),
    sort=st.sampled_from(list(CandidateSortOrder)),
    step=st.sampled_from(THRESHOLD_STEPS),
    data=st.data(),
)
def test_new_cards_stand_where_the_whole_set_sorted_afresh_puts_them(
    cards: list[OrderedCard],
    sort: CandidateSortOrder,
    step: float | None,
    data: st.DataObject,
) -> None:
    new_ids = set(data.draw(st.lists(
        st.sampled_from([c.phrase_id for c in cards]), min_size=1, unique=True,
    )))
    order = _opened([c for c in cards if c.phrase_id not in new_ids], sort, step)
    rows = _Rows(cards)
    fresh = list(ReviewOrdering.held(sort_cards(
        cards, sort, stored_standing(step), usage_order=USAGE_ORDER, source_order=SOURCES,
    ), step))

    placed = _ordering(rows, step).placed(
        order, SOURCES, sort, step,
        {c.phrase_id: c.word_id for c in cards if c.phrase_id in new_ids},
    )

    assert list(placed.cards) == list(place_new(order, fresh, new_ids).cards)
    assert placed.sectioned == order.sectioned


def test_only_the_words_of_the_new_cards_and_the_compared_ones_are_read() -> None:
    cards = [
        OrderedCard(
            phrase_id=word_id, word_id=word_id, source_id=1, lemma=f"w{word_id}", pos="NOUN",
            zipf_frequency=4.0, cefr_level="B1", occurrences=word_id % 7 + 1,
            is_phrasal_verb=False, usage_distribution=None, place=(word_id, 0, 0),
            is_done=False, sections=SectionsByStep((CandidateSection.READY,) * STEPS),
            new_counts=NewCountsByStep((0,) * STEPS),
        )
        for word_id in range(1, 1025)
    ]
    new = replace(cards[500], phrase_id=5000, word_id=5000, lemma="fresh")
    rows = _Rows([*cards, new])
    order = _opened(cards, CandidateSortOrder.RELEVANCE, None)

    _ordering(rows, None).placed(
        order, (1,), CandidateSortOrder.RELEVANCE, None, {5000: 5000},
    )

    assert len(rows.words_read) <= 1 + 11, "the new card's word and one per halving"
