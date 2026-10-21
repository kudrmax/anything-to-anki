"""Canonical sort functions for the cards of the review list.

These are the ONLY place where card ordering logic lives.
Repositories return cards unsorted; use cases call these functions.

A card is a shown phrase of a word. The cards of one word always stand together: the word
takes the place of its best card, and its other cards follow it. Sections come first, so
cards of one word in different sections stand together within each section. Done cards
are in Reviewed, the last section.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.candidate_sections import (
    SECTION_ORDER,
    card_section,
    is_junk,
    new_words,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.ordered_card import OrderedCard
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.usage_distribution import UsageDistribution
    from backend.domain.value_objects.user_knowledge import UserKnowledge

type SortKey = tuple[float | int | bool, ...]
# A card's place in a review order: its partition, the key of its word's best card there,
# its word, its own key and its phrase. Sorted by it, the cards stand as `sort_cards` puts
# them; no two cards share one.
type OrderKey = tuple[int, SortKey, int, SortKey, int]
type _Ranking[C] = tuple[Callable[[C], int], Callable[[C], SortKey]]


@dataclass(frozen=True)
class CardStanding:
    """What the user knows tells of a card: whether it is done, its section, and how many
    other words of its phrase are new."""

    is_done: bool
    section: CandidateSection
    new_words: int


class SortableCard(Protocol):
    """What the sort keys read of a card: the facts of its word and the place of its phrase.
    `place`: (block, start_line, start_char) in its document, None without one."""

    @property
    def phrase_id(self) -> int: ...

    @property
    def word_id(self) -> int: ...

    @property
    def source_id(self) -> int: ...

    @property
    def lemma(self) -> str: ...

    @property
    def pos(self) -> str: ...

    @property
    def zipf_frequency(self) -> float: ...

    @property
    def frequency_band(self) -> FrequencyBand: ...

    @property
    def cefr_level(self) -> str | None: ...

    @property
    def occurrences(self) -> int: ...

    @property
    def is_phrasal_verb(self) -> bool: ...

    @property
    def usage_distribution(self) -> UsageDistribution | None: ...

    @property
    def place(self) -> tuple[int, int, int] | None: ...


type StandingOf[C] = Callable[[C], CardStanding]


def live_standing(
    knowledge: UserKnowledge | None, frequent_threshold: FrequentWordThreshold | None,
) -> StandingOf[ReviewCard]:
    """Each card's standing computed from its phrase and what the user knows."""
    return lambda card: CardStanding(
        is_done=card.is_done,
        section=card_section(card, knowledge, frequent_threshold),
        new_words=len(new_words(card.phrase, knowledge)),
    )


def stored_standing(step: float | None) -> StandingOf[OrderedCard]:
    """Each card's standing as the projection stored it, at the threshold step `step`."""
    return lambda card: CardStanding(
        is_done=card.is_done,
        section=card.sections.at(step),
        new_words=card.new_counts.at(step),
    )


def sort_cards[C: SortableCard](
    cards: list[C],
    order: CandidateSortOrder,
    standing: StandingOf[C],
    *,
    usage_order: list[str] | None,
    source_order: Sequence[int],
) -> list[C]:
    """The cards in the review order `order`, each standing as `standing` says."""
    keys = order_keys(
        cards, order, standing, usage_order=usage_order, source_order=source_order,
    )
    return sorted(cards, key=lambda c: keys[c.phrase_id])


def order_keys[C: SortableCard](
    cards: Sequence[C],
    order: CandidateSortOrder,
    standing: StandingOf[C],
    *,
    usage_order: list[str] | None,
    source_order: Sequence[int],
) -> dict[int, OrderKey]:
    """Phrase id → the card's place in the review order `order`, as `sort_cards` sorts by
    it. A card's key reads only the cards of its own word, so it is exact for every card
    whose word's cards are all given: a few cards can be placed without the whole set."""
    if order == CandidateSortOrder.CHRONOLOGICAL:
        ranking = _chronological_ranking(cards, source_order, lambda c: standing(c).is_done)
    elif order == CandidateSortOrder.KEY_WORDS:
        ranking = _key_words_ranking(cards, standing)
    else:
        ranking = _relevance_ranking(cards, standing, usage_order)
    return _grouped_keys(cards, *ranking)

_CEFR_ORDER: dict[str | None, int] = {
    "A1": 1, "A2": 2,
    "B1": 3, "B2": 4,
    "C1": 5, "C2": 6,
    None: 99,
}
_UNPLACED = 99

_NEUTRAL = "neutral"
_OPEN, _REVIEWED = 0, 1


def _cefr_sort_key(cefr_level: str | None) -> int:
    return _CEFR_ORDER.get(cefr_level, _UNPLACED)


def _usage_sort_key(card: SortableCard, usage_order: list[str] | None) -> int:
    if usage_order is None:
        return 0
    usage = card.usage_distribution
    if usage is None:
        try:
            return usage_order.index(_NEUTRAL)
        except ValueError:
            return len(usage_order)
    return usage.rank(usage_order)


def sort_by_relevance(
    cards: list[ReviewCard],
    usage_order: list[str] | None = None,
    frequent_threshold: FrequentWordThreshold | None = None,
    knowledge: UserKnowledge | None = None,
) -> list[ReviewCard]:
    """Sort cards so the ones most worth learning come first.

    By section: ready, extra new words, probably known (junk at its bottom),
    then the done cards in Reviewed. In extra, fewer new words first; regular
    words before phrasal verbs.

    Then:
    1. frequency_band DESC — more frequent bands first
    2. usage_rank ASC — higher-priority usage group first (if usage_order given)
    3. cefr_level ASC — easier levels first; None sorts after C2
    4. occurrences DESC — more occurrences in source text first
    """
    return _by_relevance(cards, live_standing(knowledge, frequent_threshold), usage_order)


def _by_relevance[C: SortableCard](
    cards: list[C], standing: StandingOf[C], usage_order: list[str] | None,
) -> list[C]:
    return _grouped(cards, *_relevance_ranking(cards, standing, usage_order))


def _relevance_ranking[C: SortableCard](
    cards: Sequence[C], standing: StandingOf[C], usage_order: list[str] | None,
) -> _Ranking[C]:
    stood = {c.phrase_id: standing(c) for c in cards}
    return (
        lambda c: SECTION_ORDER[stood[c.phrase_id].section],
        lambda c: (
            is_junk(c),
            stood[c.phrase_id].new_words,
            c.is_phrasal_verb,
            -c.frequency_band.value,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.cefr_level),
            -c.occurrences,
        ),
    )


def sort_by_key_words(
    cards: list[ReviewCard],
    frequent_threshold: FrequentWordThreshold | None = None,
    knowledge: UserKnowledge | None = None,
) -> list[ReviewCard]:
    """Sort cards so the words this text leans on most come first.

    Meant for preparing to read: the words that keep coming back in the
    text and are rare in the language. Sections as in ``sort_by_relevance``.

    Inside a section:
    1. occurrences DESC — more occurrences in source text first
    2. zipf_frequency ASC — rarer in the language first
    3. fewer new words in the phrase first
    """
    return _by_key_words(cards, live_standing(knowledge, frequent_threshold))


def _by_key_words[C: SortableCard](cards: list[C], standing: StandingOf[C]) -> list[C]:
    return _grouped(cards, *_key_words_ranking(cards, standing))


def _key_words_ranking[C: SortableCard](
    cards: Sequence[C], standing: StandingOf[C],
) -> _Ranking[C]:
    stood = {c.phrase_id: standing(c) for c in cards}
    return (
        lambda c: SECTION_ORDER[stood[c.phrase_id].section],
        lambda c: (
            is_junk(c),
            -c.occurrences,
            c.zipf_frequency,
            stood[c.phrase_id].new_words,
        ),
    )


def sort_chronologically(
    cards: list[ReviewCard], source_order: Sequence[int],
) -> list[ReviewCard]:
    """By the place of their source in the set, then in the order their phrases stand in
    the document; phrases without a place go last in their source.

    Done cards are in Reviewed, below every open card, so the phrase waiting for a decision
    stays where the user looks.
    """
    return _chronological(cards, source_order, lambda c: c.is_done)


def _chronological[C: SortableCard](
    cards: list[C], source_order: Sequence[int], is_done: Callable[[C], bool],
) -> list[C]:
    return _grouped(cards, *_chronological_ranking(cards, source_order, is_done))


def _chronological_ranking[C: SortableCard](
    cards: Sequence[C], source_order: Sequence[int], is_done: Callable[[C], bool],
) -> _Ranking[C]:
    rank = {source_id: i for i, source_id in enumerate(source_order)}
    reviewed = {c.phrase_id for c in cards if is_done(c)}

    def _position_key(c: C) -> SortKey:
        source_rank = rank[c.source_id]
        place = c.place
        if place is None:
            return (source_rank, True, 0, 0, 0)
        return (source_rank, False, *place)

    return (lambda c: _REVIEWED if c.phrase_id in reviewed else _OPEN, _position_key)


def _grouped[C: SortableCard](
    cards: list[C], partition: Callable[[C], int], key: Callable[[C], SortKey],
) -> list[C]:
    keys = _grouped_keys(cards, partition, key)
    return sorted(cards, key=lambda c: keys[c.phrase_id])


def _grouped_keys[C: SortableCard](
    cards: Sequence[C], partition: Callable[[C], int], key: Callable[[C], SortKey],
) -> dict[int, OrderKey]:
    """Cards by partition, then by word — placed by its best card in the partition — then
    by card: the cards of one word stand together inside each partition."""
    parts = {c.phrase_id: partition(c) for c in cards}
    keys = {c.phrase_id: key(c) for c in cards}
    best: dict[tuple[int, int], SortKey] = {}
    for c in cards:
        group = (parts[c.phrase_id], c.word_id)
        if group not in best or keys[c.phrase_id] < best[group]:
            best[group] = keys[c.phrase_id]
    return {
        c.phrase_id: (
            parts[c.phrase_id],
            best[(parts[c.phrase_id], c.word_id)],
            c.word_id,
            keys[c.phrase_id],
            c.phrase_id,
        )
        for c in cards
    }
