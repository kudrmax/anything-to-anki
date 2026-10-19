from __future__ import annotations

from dataclasses import dataclass

from backend.domain.value_objects.cefr_level import CEFRLevel

OXFORD = "Oxford 5000"
CAMBRIDGE = "Cambridge Dictionary"
CEFRPY = "CEFRpy"
KELLY = "Kelly List"
EFLLEX = "EFLLex"
LEVEL_SOURCES = (OXFORD, CAMBRIDGE, CEFRPY, KELLY)
EFLLEX_PRECISION = 4


@dataclass(frozen=True)
class SourceVote:
    """A single CEFR source's evaluation of a word."""

    source_name: str
    distribution: dict[CEFRLevel, float]
    top_level: CEFRLevel  # argmax of distribution


@dataclass(frozen=True)
class ReducedBreakdown:
    """What is kept of a breakdown: the top level of each source that gives one, and the
    EFLLex distribution, rounded. Two breakdowns that keep the same are the same."""

    levels: tuple[tuple[str, str | None], ...]
    efllex: tuple[tuple[str, float], ...]

    def level_of(self, source_name: str) -> str | None:
        return dict(self.levels).get(source_name)


@dataclass(frozen=True)
class CEFRBreakdown:
    """Full breakdown of how a CEFR level was determined."""

    final_level: CEFRLevel
    decision_method: str  # "priority" | "voting"
    priority_votes: list[SourceVote]
    votes: list[SourceVote]

    def reduced(self) -> ReducedBreakdown:
        by_source = {vote.source_name: vote for vote in [*self.priority_votes, *self.votes]}
        levels = tuple(
            (name, _level_name(by_source[name].top_level) if name in by_source else None)
            for name in LEVEL_SOURCES
        )
        efllex = by_source.get(EFLLEX)
        distribution = (
            tuple(sorted(
                (level.name, round(probability, EFLLEX_PRECISION))
                for level, probability in efllex.distribution.items()
                if level is not CEFRLevel.UNKNOWN and probability > 0
            ))
            if efllex is not None
            else ()
        )
        return ReducedBreakdown(levels=levels, efllex=distribution)


def _level_name(level: CEFRLevel) -> str | None:
    return None if level is CEFRLevel.UNKNOWN else level.name
