from __future__ import annotations

from pydantic import BaseModel


class SourceVoteDTO(BaseModel):
    """A single CEFR source's evaluation."""

    source_name: str
    level: str | None  # "B1" or null if UNKNOWN
    distribution: dict[str, float] | None = None  # Only for EFLLex


class CEFRBreakdownDTO(BaseModel):
    """Full breakdown of how a CEFR level was determined."""

    decision_method: str  # "priority" | "voting"
    priority_vote: SourceVoteDTO | None = None
    votes: list[SourceVoteDTO]
