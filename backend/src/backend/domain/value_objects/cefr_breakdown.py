from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_level import CEFRLevel


@dataclass(frozen=True)
class SourceVote:
    """A single CEFR source's evaluation of a word."""

    source_name: str
    distribution: dict[CEFRLevel, float]
    top_level: CEFRLevel  # argmax of distribution


@dataclass(frozen=True)
class CEFRBreakdown:
    """Full breakdown of how a CEFR level was determined."""

    final_level: CEFRLevel
    decision_method: str  # "priority" | "voting"
    priority_votes: list[SourceVote]
    votes: list[SourceVote]
