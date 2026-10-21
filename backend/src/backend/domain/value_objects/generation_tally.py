"""The cards of one source that one kind of generation is made for, counted by what tells
their generation state, read from the stored projection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.generation_kind import GenerationKind


@dataclass(frozen=True)
class GenerationGroup:
    """Covered cards alike for one kind — words, for a kind of a word: whether the result
    is made, whether a job of the kind is active or failed for them. `cards`: how many;
    `ready`: how many of them want ready generation."""

    done: bool
    active_job: bool
    failed_job: bool
    cards: int
    ready: int


@dataclass(frozen=True)
class GenerationTally:
    """Every kind's groups of one source; a kind with no covered card has none."""

    groups: Mapping[GenerationKind, tuple[GenerationGroup, ...]]

    def of(self, kind: GenerationKind) -> tuple[GenerationGroup, ...]:
        return self.groups.get(kind, ())


EMPTY_GENERATION_TALLY = GenerationTally({})
