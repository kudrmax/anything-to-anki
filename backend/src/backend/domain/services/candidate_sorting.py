"""Canonical sort functions for word candidates.

These are the ONLY place where candidate ordering logic lives.
Repositories return candidates unsorted; use cases call these functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold

_CEFR_ORDER: dict[str | None, int] = {
    "A1": 1, "A2": 2,
    "B1": 3, "B2": 4,
    "C1": 5, "C2": 6,
    None: 99,
}

_NEUTRAL = "neutral"
_JUNK_POS: frozenset[str] = frozenset({"INTJ"})
_MISSING_FROM_DICTIONARY_ZIPF: float = 0.0
_WORD_SEPARATOR = " "


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
) -> list[StoredCandidate]:
    """Sort candidates so the cards most worth learning come first.

    Probably useless cards go down instead of disappearing. Groups, top to bottom:
    1. clean phrases, regular words before phrasal verbs
    2. phrases with other unknown words — fewer unknowns first
    3. words at or above `frequent_threshold` — probably known
    4. junk: interjections and words missing from the frequency dictionary

    Inside a group:
    1. frequency_band DESC — more frequent bands first
    2. usage_rank ASC — higher-priority usage group first (if usage_order given)
    3. cefr_level ASC — easier levels first; None sorts after C2
    4. occurrences DESC — more occurrences in source text first
    """
    return sorted(
        candidates,
        key=lambda c: (
            _is_junk(c),
            frequent_threshold is not None and frequent_threshold.covers(c.zipf_frequency),
            c.fragment_unknown_count,
            c.is_phrasal_verb,
            -c.frequency_band.value,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.cefr_level),
            -c.occurrences,
        ),
    )


def _is_junk(candidate: StoredCandidate) -> bool:
    if candidate.pos in _JUNK_POS:
        return True
    is_single_word = _WORD_SEPARATOR not in candidate.lemma
    return is_single_word and candidate.zipf_frequency <= _MISSING_FROM_DICTIONARY_ZIPF


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


def decided_last(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    """Move decided candidates below pending ones, keeping the order inside each group.

    The phrase waiting for a decision stays where the user looks, decided ones sink.
    """
    return sorted(candidates, key=lambda c: c.status != CandidateStatus.PENDING)
