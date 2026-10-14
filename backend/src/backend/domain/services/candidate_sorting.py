"""Canonical sort functions for word candidates.

These are the ONLY place where candidate ordering logic lives.
Repositories return candidates unsorted; use cases call these functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import (
    SECTION_ORDER,
    is_junk,
    new_words,
    section_of,
)
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.user_knowledge import UserKnowledge

_CEFR_ORDER: dict[str | None, int] = {
    "A1": 1, "A2": 2,
    "B1": 3, "B2": 4,
    "C1": 5, "C2": 6,
    None: 99,
}

_NEUTRAL = "neutral"


def _cefr_sort_key(cefr_level: str | None) -> int:
    return _CEFR_ORDER.get(cefr_level, 99)


def _usage_sort_key(candidate: StoredCandidate, usage_order: list[str] | None) -> int:
    if usage_order is None:
        return 0
    if candidate.usage_distribution is None:
        try:
            return usage_order.index(_NEUTRAL)
        except ValueError:
            return len(usage_order)
    return candidate.usage_distribution.rank(usage_order)


def sort_by_relevance(
    candidates: list[StoredCandidate],
    usage_order: list[str] | None = None,
    frequent_threshold: FrequentWordThreshold | None = None,
    knowledge: UserKnowledge | None = None,
) -> list[StoredCandidate]:
    """Sort candidates so the cards most worth learning come first.

    By section: ready, extra new words, probably known (junk at its bottom).
    Decided cards go below pending ones of their section. In extra, fewer new
    words first; regular words before phrasal verbs.

    Then:
    1. frequency_band DESC — more frequent bands first
    2. usage_rank ASC — higher-priority usage group first (if usage_order given)
    3. cefr_level ASC — easier levels first; None sorts after C2
    4. occurrences DESC — more occurrences in source text first
    """
    return sorted(
        candidates,
        key=lambda c: (
            *_section_key(c, knowledge, frequent_threshold),
            len(new_words(c, knowledge)),
            c.is_phrasal_verb,
            -c.frequency_band.value,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.cefr_level),
            -c.occurrences,
        ),
    )


def sort_by_key_words(
    candidates: list[StoredCandidate],
    frequent_threshold: FrequentWordThreshold | None = None,
    knowledge: UserKnowledge | None = None,
) -> list[StoredCandidate]:
    """Sort candidates so the words this text leans on most come first.

    Meant for preparing to read: the words that keep coming back in the
    text and are rare in the language. Sections as in ``sort_by_relevance``.

    Inside a section:
    1. occurrences DESC — more occurrences in source text first
    2. zipf_frequency ASC — rarer in the language first
    3. fewer new words in the phrase first
    """
    return sorted(
        candidates,
        key=lambda c: (
            *_section_key(c, knowledge, frequent_threshold),
            -c.occurrences,
            c.zipf_frequency,
            len(new_words(c, knowledge)),
        ),
    )


def _section_key(
    candidate: StoredCandidate,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> tuple[int, bool, bool]:
    section = section_of(candidate, knowledge, frequent_threshold)
    return (
        SECTION_ORDER[section],
        candidate.status != CandidateStatus.PENDING,
        is_junk(candidate),
    )


def sort_chronologically(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    """In the order their phrases stand in the document; phrases without a place go last."""

    def _position_key(c: StoredCandidate) -> tuple[bool, int, int, int, int]:
        place = c.phrase_position
        if place is None:
            return (True, 0, 0, 0, c.id or 0)
        return (False, place.block, place.start_line, place.start_char, c.id or 0)

    return sorted(candidates, key=_position_key)


def decided_last(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    """Move decided candidates below pending ones, keeping the order inside each group.

    The phrase waiting for a decision stays where the user looks, decided ones sink.
    """
    return sorted(candidates, key=lambda c: c.status != CandidateStatus.PENDING)
