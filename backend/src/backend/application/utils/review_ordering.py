from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sorting import (
    order_keys,
    sort_with_keys,
    stored_standing,
)
from backend.domain.services.review_layout import place_by_key
from backend.domain.value_objects.review_order import HeldCard

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.services.candidate_sorting import OrderKey
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    from backend.domain.value_objects.ordered_card import OrderedCard
    from backend.domain.value_objects.review_order import ReviewOrder


class ReviewOrdering:
    """The order a review of a set of sources has now, from the stored card states: what it
    opens with, and what the cards that come while it is open are placed by."""

    def __init__(
        self,
        card_states: CardStateQuery,
        threshold_resolver: FrequentWordThresholdResolver,
        candidate_sorter: CandidateSorter,
    ) -> None:
        self._card_states = card_states
        self._threshold_resolver = threshold_resolver
        self._candidate_sorter = candidate_sorter

    def step(self) -> float | None:
        """The threshold step the cards' sections are read at now."""
        return self._threshold_resolver.resolve().zipf

    def sorted_cards(
        self, source_ids: Sequence[int], sort: CandidateSortOrder, step: float | None,
    ) -> list[OrderedCard]:
        """Every card of the sources in the review's order at the step; `source_ids` in the
        set's order."""
        return [card for card, _ in self.ordered(source_ids, sort, step)]

    def ordered(
        self, source_ids: Sequence[int], sort: CandidateSortOrder, step: float | None,
    ) -> list[tuple[OrderedCard, OrderKey]]:
        """`sorted_cards`, each card with the key it is sorted by."""
        return sort_with_keys(
            self._card_states.order_rows(source_ids), sort, stored_standing(step),
            usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
        )

    def placed(
        self,
        order: ReviewOrder,
        source_ids: Sequence[int],
        sort: CandidateSortOrder,
        step: float | None,
        new_words: Mapping[int, int],
    ) -> ReviewOrder:
        """The new cards (phrase id → word id) placed into the held order by their keys now,
        each in its section now, against the keys the held cards were held by. Reads only
        the cards of the new cards' words."""
        rows = [
            row for row in self._card_states.order_rows_of_words(set(new_words.values()))
            if row.source_id in set(source_ids)
        ]
        keys = order_keys(
            rows, sort, stored_standing(step),
            usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
        )
        return place_by_key(order, [
            HeldCard(row.phrase_id, row.word_id, row.sections.at(step), keys[row.phrase_id])
            for row in rows if row.phrase_id in new_words
        ])

    @staticmethod
    def held(
        cards: Iterable[OrderedCard],
        step: float | None,
        keys: Mapping[int, OrderKey] | None = None,
    ) -> Iterator[HeldCard]:
        """The cards as an order holds them: each in its section at the step, with its key
        when `keys` gives them."""
        return (
            HeldCard(
                c.phrase_id, c.word_id, c.sections.at(step),
                None if keys is None else keys[c.phrase_id],
            )
            for c in cards
        )
