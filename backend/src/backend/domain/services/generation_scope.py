"""Which cards a generation scope takes, by their generation state and readiness."""
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope

if TYPE_CHECKING:
    from collections.abc import Mapping

_MISSING = frozenset({CardGenerationState.MISSING})

# Cards already being generated are left alone in every scope: their job is about to
# deliver a fresh result anyway, and a second job would only duplicate the work.
STATES_IN_SCOPE: Mapping[GenerationScope, frozenset[CardGenerationState]] = MappingProxyType({
    GenerationScope.MISSING: _MISSING,
    GenerationScope.READY_MISSING: _MISSING,
    GenerationScope.FAILED: frozenset({CardGenerationState.FAILED}),
    GenerationScope.ALL: frozenset({
        CardGenerationState.DONE, CardGenerationState.FAILED, CardGenerationState.MISSING,
    }),
})
_TAKES_ONLY_READY: Mapping[GenerationScope, bool] = MappingProxyType({
    GenerationScope.MISSING: False,
    GenerationScope.READY_MISSING: True,
    GenerationScope.FAILED: False,
    GenerationScope.ALL: False,
})


def in_scope(scope: GenerationScope, state: CardGenerationState, ready: bool) -> bool:
    """`ready`: the card wants ready generation (`card_view.wants_ready_generation`)."""
    return state in STATES_IN_SCOPE[scope] and (ready or not _TAKES_ONLY_READY[scope])
