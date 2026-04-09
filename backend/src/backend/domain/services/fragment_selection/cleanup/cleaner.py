"""Rule-driven boundary cleaner — loops over enabled StripRules."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.cleanup.rules import Edge
from backend.domain.services.fragment_selection.registry import build_strip_rules
from backend.domain.value_objects.fragment_selection_config import CleanupConfig

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.services.fragment_selection.cleanup.rules import StripRule


class RuleDrivenBoundaryCleaner:
    """Trims dangling function words from the edges of a fragment, driven
    by an ordered list of ``StripRule`` classes enabled in config.

    Stops if cleaning would drop the fragment below the configured minimum
    content-word count or remove a token marked as protected.
    """

    def __init__(self, config: CleanupConfig | None = None) -> None:
        self._config = config or CleanupConfig()
        self._rules: list[StripRule] = build_strip_rules(self._config)

    def clean(
        self,
        tokens: list[TokenData],
        indices: list[int],
        protected_indices: frozenset[int] = frozenset(),
    ) -> list[int]:
        if not indices:
            return list(indices)

        result = sorted(set(indices))

        while result and self._try_strip(tokens, result, Edge.LEFT, protected_indices):
            result = result[1:]

        while result and self._try_strip(
            tokens, result, Edge.RIGHT, protected_indices
        ):
            result = result[:-1]

        return result

    def _try_strip(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
        protected: frozenset[int],
    ) -> bool:
        edge_idx = indices[0] if edge is Edge.LEFT else indices[-1]
        if edge_idx in protected:
            return False
        return any(rule.applies(tokens, indices, edge) for rule in self._rules)
