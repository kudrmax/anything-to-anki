"""Canonical sort functions for the cards of the review list.

These are the ONLY place where card ordering logic lives.
Repositories return cards unsorted; use cases call these functions.

A card is a shown phrase of a word. The cards of one word always stand together: the word
takes the place of its best card, and its other cards follow it. Sections come first, so
cards of one word in different sections stand together within each section. Done cards
are in Reviewed, the last section.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import (
    SECTION_ORDER,
    card_section,
    is_junk,
    new_words,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.user_knowledge import UserKnowledge

type SortKey = tuple[float | int | bool, ...]

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


def _usage_sort_key(card: ReviewCard, usage_order: list[str] | None) -> int:
    if usage_order is None:
        return 0
    usage = card.word.usage_distribution
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
    return _grouped(
        cards,
        partition=lambda c: SECTION_ORDER[card_section(c, knowledge, frequent_threshold)],
        key=lambda c: (
            is_junk(c),
            len(new_words(c.phrase, knowledge)),
            c.word.is_phrasal_verb,
            -c.frequency_band.value,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.word.cefr_level),
            -c.word.occurrences,
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
    return _grouped(
        cards,
        partition=lambda c: SECTION_ORDER[card_section(c, knowledge, frequent_threshold)],
        key=lambda c: (
            is_junk(c),
            -c.word.occurrences,
            c.zipf_frequency,
            len(new_words(c.phrase, knowledge)),
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
    rank = {source_id: i for i, source_id in enumerate(source_order)}

    def _position_key(c: ReviewCard) -> SortKey:
        source_rank = rank[c.word.source_id]
        place = c.occurrence.phrase_position
        if place is None:
            return (source_rank, True, 0, 0, 0)
        return (source_rank, False, place.block, place.start_line, place.start_char)

    return _grouped(
        cards, partition=lambda c: _REVIEWED if c.is_done else _OPEN, key=_position_key,
    )


def _grouped(
    cards: list[ReviewCard],
    *,
    partition: Callable[[ReviewCard], int],
    key: Callable[[ReviewCard], SortKey],
) -> list[ReviewCard]:
    """Cards by partition, then by word — placed by its best card in the partition — then
    by card: the cards of one word stand together inside each partition."""
    parts = {c.phrase_id: partition(c) for c in cards}
    keys = {c.phrase_id: key(c) for c in cards}
    best: dict[tuple[int, int], SortKey] = {}
    for c in cards:
        group = (parts[c.phrase_id], c.word_id)
        if group not in best or keys[c.phrase_id] < best[group]:
            best[group] = keys[c.phrase_id]
    return sorted(
        cards,
        key=lambda c: (
            parts[c.phrase_id],
            best[(parts[c.phrase_id], c.word_id)],
            c.word_id,
            keys[c.phrase_id],
            c.phrase_id,
        ),
    )
