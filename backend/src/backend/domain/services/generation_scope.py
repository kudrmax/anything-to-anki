"""Which cards a generation scope takes, by their generation state and readiness."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from backend.domain.value_objects.generation_tally import GenerationGroup

_MISSING = frozenset({CardGenerationState.MISSING})
_ALL = frozenset({
    CardGenerationState.DONE, CardGenerationState.FAILED, CardGenerationState.MISSING,
})

# Cards already being generated are left alone in every scope: their job is about to
# deliver a fresh result anyway, and a second job would only duplicate the work.
STATES_IN_SCOPE: Mapping[GenerationScope, frozenset[CardGenerationState]] = MappingProxyType({
    GenerationScope.NEXT: _MISSING,
    GenerationScope.MISSING: _MISSING,
    GenerationScope.READY_NEXT: _MISSING,
    GenerationScope.READY_MISSING: _MISSING,
    GenerationScope.FAILED: frozenset({CardGenerationState.FAILED}),
    GenerationScope.READY_ALL: _ALL,
    GenerationScope.ALL: _ALL,
})
_TAKES_ONLY_READY: Mapping[GenerationScope, bool] = MappingProxyType({
    GenerationScope.NEXT: False,
    GenerationScope.MISSING: False,
    GenerationScope.READY_NEXT: True,
    GenerationScope.READY_MISSING: True,
    GenerationScope.READY_ALL: True,
    GenerationScope.FAILED: False,
    GenerationScope.ALL: False,
})

_REPLACES_RESULTS = frozenset({GenerationScope.READY_ALL, GenerationScope.ALL})
_TAKES_BATCH = frozenset({GenerationScope.NEXT, GenerationScope.READY_NEXT})


def in_scope(scope: GenerationScope, state: CardGenerationState, ready: bool) -> bool:
    """`ready`: the card wants ready generation (`card_view.wants_ready_generation`)."""
    return state in STATES_IN_SCOPE[scope] and (ready or not _TAKES_ONLY_READY[scope])


def replaces_results(scope: GenerationScope) -> bool:
    """The scope makes the result anew: what the cards have is discarded first."""
    return scope in _REPLACES_RESULTS


def takes_batch(scope: GenerationScope) -> bool:
    """The scope takes a batch at most: the first cards in the list's order."""
    return scope in _TAKES_BATCH


def in_batch(cards: int, batch_size: int) -> int:
    """How many of `cards` a scope that takes a batch takes."""
    return min(cards, batch_size)


def generation_state(*, active_job: bool, done: bool, failed_job: bool) -> CardGenerationState:
    """A job on its way beats the result, the result beats a failed job."""
    if active_job:
        return CardGenerationState.RUNNING
    if done:
        return CardGenerationState.DONE
    if failed_job:
        return CardGenerationState.FAILED
    return CardGenerationState.MISSING


@dataclass(frozen=True)
class GenerationCounts:
    """How far one kind got over the cards it is made for: `total` split by state, and how
    many cards each scope would take."""

    total: int = 0
    done: int = 0
    running: int = 0
    failed: int = 0
    missing: int = 0
    ready_missing: int = 0
    ready_all: int = 0
    all: int = 0

    def __add__(self, other: GenerationCounts) -> GenerationCounts:
        return GenerationCounts(*(
            getattr(self, f.name) + getattr(other, f.name) for f in fields(self)
        ))


_COUNTED_SCOPES: tuple[GenerationScope, ...] = (
    GenerationScope.READY_MISSING, GenerationScope.READY_ALL, GenerationScope.ALL,
)


def generation_counts(groups: Iterable[GenerationGroup]) -> GenerationCounts:
    """The counts of cards tallied in groups alike in what tells their state."""
    states: Counter[CardGenerationState] = Counter()
    taken: Counter[GenerationScope] = Counter()
    for group in groups:
        state = generation_state(
            active_job=group.active_job, done=group.done, failed_job=group.failed_job,
        )
        states[state] += group.cards
        for scope in _COUNTED_SCOPES:
            taken[scope] += (
                group.ready * in_scope(scope, state, ready=True)
                + (group.cards - group.ready) * in_scope(scope, state, ready=False)
            )
    return GenerationCounts(
        total=states.total(),
        done=states[CardGenerationState.DONE],
        running=states[CardGenerationState.RUNNING],
        failed=states[CardGenerationState.FAILED],
        missing=states[CardGenerationState.MISSING],
        ready_missing=taken[GenerationScope.READY_MISSING],
        ready_all=taken[GenerationScope.READY_ALL],
        all=taken[GenerationScope.ALL],
    )
