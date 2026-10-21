"""What background generation made for a card so far, as the ✨ menu counts it."""
from __future__ import annotations

from dataclasses import dataclass

from backend.domain.value_objects.generation_kind import GenerationKind


@dataclass(frozen=True)
class GeneratedParts:
    """`done`: the kinds whose result the card has (a kind of a word: its word has it).
    `uncovered`: the kinds the card cannot get at all, in play or not (a clip needs the
    phrase's timecodes in the video)."""

    done: frozenset[GenerationKind]
    uncovered: frozenset[GenerationKind]

    def __post_init__(self) -> None:
        if not self.uncovered <= COVERAGE_KINDS:
            msg = f"only {sorted(COVERAGE_KINDS)} may leave a card uncovered"
            raise ValueError(msg)


# The kinds that cover only some of the cards in play.
COVERAGE_KINDS: frozenset[GenerationKind] = frozenset({GenerationKind.MEDIA})
NOTHING_GENERATED = GeneratedParts(frozenset(), frozenset())
