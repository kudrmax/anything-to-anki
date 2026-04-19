"""Canonical sort functions for word candidates.

These are the ONLY place where candidate ordering logic lives.
Repositories return candidates unsorted; use cases call these functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate

# CEFR sort key: A1=1 .. C2=6, None=99 (after everything)
_CEFR_ORDER: dict[str | None, int] = {
    "A1": 1, "A2": 2,
    "B1": 3, "B2": 4,
    "C1": 5, "C2": 6,
    None: 99,
}


def _cefr_sort_key(cefr_level: str | None) -> int:
    return _CEFR_ORDER.get(cefr_level, 99)


def sort_by_relevance(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    """Sort candidates by relevance for learning.

    Priority (all within the same level win over the next level):
    1. frequency_band DESC — more frequent bands first
    2. is_phrasal_verb DESC — phrasal verbs first within same band
    3. cefr_level ASC — easier levels first; None sorts after C2
    4. occurrences DESC — more occurrences in source text first
    """
    return sorted(
        candidates,
        key=lambda c: (
            -c.frequency_band.value,       # band DESC (higher value = more frequent)
            not c.is_phrasal_verb,          # phrasal verbs first (False < True)
            _cefr_sort_key(c.cefr_level),   # cefr ASC, None last
            -c.occurrences,                 # occurrences DESC
        ),
    )


def sort_chronologically(
    candidates: list[StoredCandidate],
    source_text: str,
) -> list[StoredCandidate]:
    """Sort candidates by position of context_fragment in source text.

    Candidates whose fragment is not found in the text sort last.
    Tiebreaker: candidate id (insertion order).
    """
    text_len = len(source_text)

    def _position_key(c: StoredCandidate) -> tuple[int, int]:
        pos = source_text.find(c.context_fragment)
        if pos < 0:
            pos = text_len
        return (pos, c.id or 0)

    return sorted(candidates, key=_position_key)
