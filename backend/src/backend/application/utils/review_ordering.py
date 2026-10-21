from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sorting import order_keys, sort_cards, stored_standing
from backend.domain.services.review_layout import place_by_key
from backend.domain.value_objects.review_order import HeldCard

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence

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
        return sort_cards(
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
        """The new cards (phrase id → word id) placed into the held order as a fresh sort
        of the set would place them, each in its section now. Reads the cards of the new
        cards' words and of the words the binary search compares against, never the whole
        set."""
        keys = _WordKeys(self, source_ids, sort, step, frozenset(new_words))
        new_word_ids = set(new_words.values())
        keys.read(new_word_ids)
        new = [
            (HeldCard(phrase_id, word_id, keys.card(phrase_id).sections.at(step)), key)
            for phrase_id, word_id in new_words.items()
            if (key := keys.key(phrase_id)) is not None
        ]
        regrouped = {
            phrase_id: key
            for phrase_id, key in keys.of_words(new_word_ids).items()
            if order.index_of(phrase_id) is not None
        }

        def held_keys_at(indices: Collection[int]) -> dict[int, OrderKey]:
            keys.read({order.word_ids[i] for i in indices})
            found: dict[int, OrderKey] = {}
            for index in indices:
                key = keys.held_key(order.phrase_id_at(index))
                if key is not None:
                    found[index] = key
            return found

        return place_by_key(order, new, held_keys_at, regrouped)

    def keys_of(
        self,
        cards: Sequence[OrderedCard],
        source_ids: Sequence[int],
        sort: CandidateSortOrder,
        step: float | None,
    ) -> dict[int, OrderKey]:
        return order_keys(
            cards, sort, stored_standing(step),
            usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
        )

    def rows_of_words(self, word_ids: Collection[int]) -> list[OrderedCard]:
        return self._card_states.order_rows_of_words(word_ids)

    @staticmethod
    def held(cards: Iterable[OrderedCard], step: float | None) -> Iterator[HeldCard]:
        """The cards as an order holds them: each in its section at the step."""
        return (HeldCard(c.phrase_id, c.word_id, c.sections.at(step)) for c in cards)


class _WordKeys:
    """The order keys of the cards of the words read so far, a word at a time: a card's key
    reads every card of its word. Each card has its key now and the key it was held by,
    read without the new cards: they differ only for the cards of the new cards' words."""

    def __init__(
        self,
        ordering: ReviewOrdering,
        source_ids: Sequence[int],
        sort: CandidateSortOrder,
        step: float | None,
        new_ids: frozenset[int],
    ) -> None:
        self._ordering = ordering
        self._source_ids = source_ids
        self._sort = sort
        self._step = step
        self._new_ids = new_ids
        self._words: set[int] = set()
        self._cards: dict[int, OrderedCard] = {}
        self._keys: dict[int, OrderKey] = {}
        self._held_keys: dict[int, OrderKey] = {}

    def read(self, word_ids: Collection[int]) -> None:
        missing = [w for w in word_ids if w not in self._words]
        if not missing:
            return
        self._words.update(missing)
        in_set = set(self._source_ids)
        rows = [r for r in self._ordering.rows_of_words(missing) if r.source_id in in_set]
        self._cards.update((r.phrase_id, r) for r in rows)
        self._keys.update(self._keys_of(rows))
        held = [r for r in rows if r.phrase_id not in self._new_ids]
        self._held_keys.update(
            self._keys_of(held) if len(held) < len(rows)
            else {r.phrase_id: self._keys[r.phrase_id] for r in rows},
        )

    def _keys_of(self, rows: Sequence[OrderedCard]) -> dict[int, OrderKey]:
        return self._ordering.keys_of(rows, self._source_ids, self._sort, self._step)

    def key(self, phrase_id: int) -> OrderKey | None:
        return self._keys.get(phrase_id)

    def held_key(self, phrase_id: int) -> OrderKey | None:
        return self._held_keys.get(phrase_id)

    def of_words(self, word_ids: Collection[int]) -> dict[int, OrderKey]:
        """The keys now of the cards of these words, read before."""
        return {
            phrase_id: self._keys[phrase_id]
            for phrase_id, card in self._cards.items() if card.word_id in word_ids
        }

    def card(self, phrase_id: int) -> OrderedCard:
        return self._cards[phrase_id]
