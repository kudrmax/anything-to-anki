"""The ✨ counts of cards tallied in groups: the state of each group and what each scope
takes, as the cards listed one by one would read."""
from __future__ import annotations

import pytest
from backend.domain.services.generation_scope import (
    GenerationCounts,
    generation_counts,
    generation_state,
    in_scope,
)
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.generation_tally import GenerationGroup


@pytest.mark.unit
@pytest.mark.parametrize(("active", "done", "failed", "state"), [
    (True, True, True, CardGenerationState.RUNNING),
    (True, False, False, CardGenerationState.RUNNING),
    (False, True, True, CardGenerationState.DONE),
    (False, True, False, CardGenerationState.DONE),
    (False, False, True, CardGenerationState.FAILED),
    (False, False, False, CardGenerationState.MISSING),
])
def test_a_job_on_its_way_beats_the_result_and_the_result_a_failed_job(
    *, active: bool, done: bool, failed: bool, state: CardGenerationState,
) -> None:
    assert generation_state(active_job=active, done=done, failed_job=failed) is state


GROUPS = (
    GenerationGroup(done=True, active_job=False, failed_job=False, cards=4, ready=1),
    GenerationGroup(done=False, active_job=True, failed_job=True, cards=3, ready=2),
    GenerationGroup(done=False, active_job=False, failed_job=True, cards=2, ready=2),
    GenerationGroup(done=False, active_job=False, failed_job=False, cards=5, ready=3),
)


@pytest.mark.unit
def test_the_counts_split_the_cards_by_state() -> None:
    assert generation_counts(GROUPS) == GenerationCounts(
        total=14, done=4, running=3, failed=2, missing=5,
        ready_missing=3, ready_all=1 + 2 + 3, all=4 + 2 + 5,
    )


@pytest.mark.unit
def test_the_scopes_count_as_the_cards_listed_one_by_one() -> None:
    listed = [
        (generation_state(active_job=g.active_job, done=g.done, failed_job=g.failed_job),
         index < g.ready)
        for g in GROUPS for index in range(g.cards)
    ]
    counts = generation_counts(GROUPS)
    for scope, counted in (
        (GenerationScope.READY_MISSING, counts.ready_missing),
        (GenerationScope.READY_ALL, counts.ready_all),
        (GenerationScope.ALL, counts.all),
    ):
        assert counted == sum(in_scope(scope, state, ready) for state, ready in listed)


@pytest.mark.unit
def test_no_cards_count_nothing() -> None:
    assert generation_counts(()) == GenerationCounts()
