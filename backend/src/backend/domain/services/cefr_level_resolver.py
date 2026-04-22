"""Resolve final CEFR level from source votes.

Pure domain logic, no I/O. Encodes the priority strategy:
min(Oxford, Cambridge) → whichever is available → weighted voting.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Final

from backend.domain.value_objects.cefr_breakdown import SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel

PRIORITY_SOURCE_NAMES: Final[list[str]] = ["Oxford 5000", "Cambridge Dictionary"]


def resolve_cefr_level(all_votes: list[SourceVote]) -> tuple[CEFRLevel, str]:
    """Determine final CEFR level from source votes.

    Strategy:
    1. If both Oxford and Cambridge know the word → take the lower level.
    2. If only one knows → take that one.
    3. If neither knows → equal-weight voting among the rest.

    Returns (level, decision_method).
    """
    oxford = _get_known_level(all_votes, "Oxford 5000")
    cambridge = _get_known_level(all_votes, "Cambridge Dictionary")

    if oxford is not None and cambridge is not None:
        level = oxford if oxford.value <= cambridge.value else cambridge
        return level, "priority"

    if oxford is not None:
        return oxford, "priority"

    if cambridge is not None:
        return cambridge, "priority"

    non_priority = [
        v for v in all_votes if v.source_name not in PRIORITY_SOURCE_NAMES
    ]
    if not non_priority:
        return CEFRLevel.UNKNOWN, "voting"

    return _weighted_vote(non_priority), "voting"


def _get_known_level(votes: list[SourceVote], name: str) -> CEFRLevel | None:
    """Return the level if the source knows the word, else None."""
    vote = _find_vote(votes, name)
    if vote is not None and vote.top_level is not CEFRLevel.UNKNOWN:
        return vote.top_level
    return None


def _find_vote(votes: list[SourceVote], name: str) -> SourceVote | None:
    for v in votes:
        if v.source_name == name:
            return v
    return None


def _weighted_vote(votes: list[SourceVote]) -> CEFRLevel:
    """Equal-weight voting. Tie-break: prefer lower (easier) level."""
    weight = 1.0 / len(votes)
    totals: dict[CEFRLevel, float] = defaultdict(float)
    for vote in votes:
        for level, prob in vote.distribution.items():
            totals[level] += prob * weight
    return max(totals, key=lambda lvl: (totals[lvl], -lvl.value))
