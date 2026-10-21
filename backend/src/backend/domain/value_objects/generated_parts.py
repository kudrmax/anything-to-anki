"""What background generation made for a card so far and what the queue holds for it, as
the ✨ menu counts it and the card shows it."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from backend.domain.value_objects.generation_kind import GenerationKind


@dataclass(frozen=True)
class GeneratedParts:
    """`done`: the kinds whose result the card has (a kind of a word: its word has it).
    `uncovered`: the kinds the card cannot get at all, in play or not (a clip needs the
    phrase's timecodes in the video). `active_jobs`: the kinds with a job queued or running
    for the card (a kind of a word: for its word); `failed_jobs`: the kinds whose job failed
    and none is on its way."""

    done: frozenset[GenerationKind]
    uncovered: frozenset[GenerationKind]
    active_jobs: frozenset[GenerationKind] = frozenset()
    failed_jobs: frozenset[GenerationKind] = frozenset()

    def __post_init__(self) -> None:
        if not self.uncovered <= COVERAGE_KINDS:
            msg = f"only {sorted(COVERAGE_KINDS)} may leave a card uncovered"
            raise ValueError(msg)
        if self.active_jobs & self.failed_jobs:
            msg = "a kind's job is either on its way or failed"
            raise ValueError(msg)

    def job_of(self, kind: GenerationKind) -> JobState:
        if kind in self.active_jobs:
            return JobState.ACTIVE
        return JobState.FAILED if kind in self.failed_jobs else JobState.NONE


class JobState(IntEnum):
    """What the queue holds for a card of one kind: no job, a failed one, one on its way."""

    NONE = 0
    FAILED = 1
    ACTIVE = 2


# The kinds that cover only some of the cards in play.
COVERAGE_KINDS: frozenset[GenerationKind] = frozenset({GenerationKind.MEDIA})
NOTHING_GENERATED = GeneratedParts(frozenset(), frozenset())
