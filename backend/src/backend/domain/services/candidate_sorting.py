"""Canonical sort functions for word candidates.

These are the ONLY place where candidate ordering logic lives.
Repositories return candidates unsorted; use cases call these functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate

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
) -> list[StoredCandidate]:
    """Sort candidates by relevance for learning.

    Priority (all within the same level win over the next level):
    1. frequency_band DESC — more frequent bands first
    2. is_phrasal_verb DESC — phrasal verbs first within same band
    3. usage_rank ASC — higher-priority usage group first (if usage_order given)
    4. cefr_level ASC — easier levels first; None sorts after C2
    5. occurrences DESC — more occurrences in source text first
    """
    return sorted(
        candidates,
        key=lambda c: (
            -c.frequency_band.value,
            not c.is_phrasal_verb,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.cefr_level),
            -c.occurrences,
        ),
    )


def sort_chronologically(
    candidates: list[StoredCandidate],
    source_text: str,
) -> list[StoredCandidate]:
    """Sort candidates by position of context_fragment in source text."""
    text_len = len(source_text)

    def _position_key(c: StoredCandidate) -> tuple[int, int]:
        pos = source_text.find(c.context_fragment)
        if pos < 0:
            pos = text_len
        return (pos, c.id or 0)

    return sorted(candidates, key=_position_key)
