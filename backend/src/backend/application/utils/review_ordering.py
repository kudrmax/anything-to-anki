from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sorting import sort_cards, stored_standing
from backend.domain.value_objects.review_order import HeldCard

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    from backend.domain.value_objects.ordered_card import OrderedCard


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
        return sort_cards(
            self._card_states.order_rows(source_ids), sort, stored_standing(step),
            usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
        )

    @staticmethod
    def held(cards: Iterable[OrderedCard], step: float | None) -> Iterator[HeldCard]:
        """The cards as an order holds them: each in its section at the step."""
        return (HeldCard(c.phrase_id, c.word_id, c.sections.at(step)) for c in cards)
