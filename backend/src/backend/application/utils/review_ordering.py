from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sorting import (
    order_keys,
    sort_with_keys,
    stored_standing,
)
from backend.domain.services.review_layout import place_by_key, remove_cards
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.review_order import HeldCard, ReviewOrder

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence

    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.services.candidate_sorting import OrderKey
    from backend.domain.value_objects.ordered_card import OrderedCard


# Past this many changed words reading their cards and placing each costs more than
# ordering the set anew.
PLACED_ONE_BY_ONE_AT_MOST = 2_000


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

    def opened(
        self, source_ids: Sequence[int], sort: CandidateSortOrder, step: float | None,
    ) -> tuple[ReviewOrder, list[OrderedCard]]:
        """The order a review opened now holds, with every card of it in that order."""
        pairs = self.ordered(source_ids, sort, step)
        cards = [card for card, _ in pairs]
        order = ReviewOrder(
            self.held(cards, step, {c.phrase_id: k for c, k in pairs}),
            sectioned=sort != CandidateSortOrder.CHRONOLOGICAL,
        )
        return order, cards

    def placed(
        self,
        order: ReviewOrder,
        source_ids: Sequence[int],
        sort: CandidateSortOrder,
        step: float | None,
        words: Collection[int],
        kept: Collection[int] = (),
    ) -> ReviewOrder:
        """The cards of these words where an order opened now puts them: a new card joins,
        a held one whose key or section changed moves, each in its section now; a `kept`
        card stays where it is. The other held cards keep their keys, so the order stays in
        key order. Reads only the cards of these words; past `PLACED_ONE_BY_ONE_AT_MOST`
        of them, orders the set anew."""
        if len(words) > PLACED_ONE_BY_ONE_AT_MOST:
            return self.opened(source_ids, sort, step)[0]
        in_set = set(source_ids)
        rows = [
            row for row in self._card_states.order_rows_of_words(set(words))
            if row.source_id in in_set
        ]
        keys = order_keys(
            rows, sort, stored_standing(step),
            usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
        )
        moved = []
        for row in rows:
            card = HeldCard(row.phrase_id, row.word_id, row.sections.at(step), keys[row.phrase_id])
            held = order.card(row.phrase_id)
            if row.phrase_id in kept and held is not None:
                continue
            if held != card or held.key != card.key:
                moved.append(card)
        if not moved:
            return order
        return place_by_key(remove_cards(order, [c.phrase_id for c in moved]), moved)

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
