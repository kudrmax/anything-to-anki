from __future__ import annotations

import pytest
from backend.domain.services.card_view import wants_ready_generation
from backend.domain.services.generation_scope import in_scope, replaces_results
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope

MISSING = CardGenerationState.MISSING


@pytest.mark.unit
class TestInScope:
    def test_ready_missing_takes_only_a_ready_missing_card(self) -> None:
        assert in_scope(GenerationScope.READY_MISSING, MISSING, ready=True)
        assert not in_scope(GenerationScope.READY_MISSING, MISSING, ready=False)
        assert not in_scope(GenerationScope.READY_MISSING, CardGenerationState.FAILED, ready=True)

    def test_ready_all_takes_any_ready_card_not_running(self) -> None:
        assert in_scope(GenerationScope.READY_ALL, CardGenerationState.DONE, ready=True)
        assert in_scope(GenerationScope.READY_ALL, CardGenerationState.FAILED, ready=True)
        assert not in_scope(GenerationScope.READY_ALL, CardGenerationState.DONE, ready=False)

    def test_only_the_all_scopes_replace_results(self) -> None:
        assert {s for s in GenerationScope if replaces_results(s)} == {
            GenerationScope.READY_ALL, GenerationScope.ALL,
        }

    def test_missing_takes_a_missing_card_ready_or_not(self) -> None:
        assert in_scope(GenerationScope.MISSING, MISSING, ready=False)

    def test_no_scope_takes_a_running_card(self) -> None:
        assert not any(
            in_scope(scope, CardGenerationState.RUNNING, ready=True) for scope in GenerationScope
        )


@pytest.mark.unit
class TestWantsReadyGeneration:
    def test_a_card_in_play_whose_phrase_earns_ready(self) -> None:
        assert wants_ready_generation(True, CandidateSection.READY)

    def test_not_a_card_out_of_play_or_outside_ready(self) -> None:
        assert not wants_ready_generation(False, CandidateSection.READY)
        assert not wants_ready_generation(True, CandidateSection.EXTRA)
