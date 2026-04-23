"""Resolve final CEFR level from source votes.

Pure domain logic, no I/O. Encodes the priority strategy:
min(priority_votes) → whichever is available → weighted voting among regular.
"""
from __future__ import annotations

from collections import defaultdict

from backend.domain.value_objects.cefr_breakdown import SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


def resolve_cefr_level(
    priority_votes: list[SourceVote],
    regular_votes: list[SourceVote],
) -> tuple[CEFRLevel, str]:
    """Determine final CEFR level from source votes.

    Strategy:
    1. Collect known levels from priority sources.
    2. If any priority sources know the word → take the lower (easier) level.
    3. If none know → equal-weight voting among regular sources.

    Returns (level, decision_method).
    """
    known_priority = [
        v.top_level for v in priority_votes
        if v.top_level is not CEFRLevel.UNKNOWN
    ]

    if known_priority:
        level = min(known_priority, key=lambda lvl: lvl.value)
        return level, "priority"

    non_unknown = [v for v in regular_votes if v.top_level is not CEFRLevel.UNKNOWN]
    if not non_unknown:
        return CEFRLevel.UNKNOWN, "voting"

    return _weighted_vote(non_unknown), "voting"


def _weighted_vote(votes: list[SourceVote]) -> CEFRLevel:
    """Equal-weight voting. Tie-break: prefer lower (easier) level."""
    weight = 1.0 / len(votes)
    totals: dict[CEFRLevel, float] = defaultdict(float)
    for vote in votes:
        for level, prob in vote.distribution.items():
            totals[level] += prob * weight
    return max(totals, key=lambda lvl: (totals[lvl], -lvl.value))
