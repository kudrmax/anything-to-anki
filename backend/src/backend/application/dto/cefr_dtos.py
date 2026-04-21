from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote


class SourceVoteDTO(BaseModel):
    """A single CEFR source's evaluation."""

    source_name: str
    level: str | None  # "B1" or null if UNKNOWN
    distribution: dict[str, float] | None = None  # Only for EFLLex


class CEFRBreakdownDTO(BaseModel):
    """Full breakdown of how a CEFR level was determined."""

    decision_method: str  # "priority" | "voting"
    priority_votes: list[SourceVoteDTO] = []
    votes: list[SourceVoteDTO]


def dto_to_breakdown(dto: CEFRBreakdownDTO) -> CEFRBreakdown:
    """Map CEFRBreakdownDTO back to domain CEFRBreakdown."""
    from backend.domain.services.cefr_level_resolver import resolve_cefr_level
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown as Bd
    from backend.domain.value_objects.cefr_breakdown import SourceVote as Sv
    from backend.domain.value_objects.cefr_level import CEFRLevel

    def _dto_to_vote(v: SourceVoteDTO) -> Sv:
        if v.distribution:
            dist = {CEFRLevel.from_str(k): prob for k, prob in v.distribution.items()}
        elif v.level:
            dist = {CEFRLevel.from_str(v.level): 1.0}
        else:
            dist = {CEFRLevel.UNKNOWN: 1.0}
        top = CEFRLevel.from_str(v.level) if v.level else CEFRLevel.UNKNOWN
        return Sv(source_name=v.source_name, distribution=dist, top_level=top)

    priority_votes = [_dto_to_vote(v) for v in dto.priority_votes]
    votes = [_dto_to_vote(v) for v in dto.votes]
    all_votes = [*priority_votes, *votes]
    final, decision_method = resolve_cefr_level(all_votes)
    return Bd(
        final_level=final,
        decision_method=decision_method,
        priority_votes=priority_votes,
        votes=votes,
    )


def breakdown_to_dto(breakdown: CEFRBreakdown) -> CEFRBreakdownDTO:
    """Map domain CEFRBreakdown to DTO."""
    from backend.domain.value_objects.cefr_level import CEFRLevel

    def _vote_to_dto(vote: SourceVote) -> SourceVoteDTO:
        top = vote.top_level
        level_str = top.name if top is not CEFRLevel.UNKNOWN else None
        dist: dict[str, float] | None = None
        if vote.source_name == "EFLLex":
            dist = {
                lvl.name: round(prob, 4)
                for lvl, prob in vote.distribution.items()
                if lvl is not CEFRLevel.UNKNOWN and prob > 0
            }
        return SourceVoteDTO(source_name=vote.source_name, level=level_str, distribution=dist)

    return CEFRBreakdownDTO(
        decision_method=breakdown.decision_method,
        priority_votes=[_vote_to_dto(v) for v in breakdown.priority_votes],
        votes=[_vote_to_dto(v) for v in breakdown.votes],
    )
