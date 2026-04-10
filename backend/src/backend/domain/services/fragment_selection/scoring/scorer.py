"""Candidate scoring for fragment selection.

``DefaultScorer`` reproduces the Wave 2 tuple
``(weight_unknown * unknowns, length_penalty, weight_content * content_count)``.
The unknown count is supplied via an ``UnknownCounter`` callable so the
domain stays free of CEFR/use-case concerns.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.fragment_selection.utils import count_content_words

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.value_objects.fragment_selection_config import ScoringConfig


type UnknownCounter = Callable[[Sequence[int], list["TokenData"]], int]


class Scorer(Protocol):
    """Protocol for candidate scoring. Lower score is better."""

    def score(
        self, indices: Sequence[int], tokens: list[TokenData]
    ) -> tuple[int, int, int, int]:
        ...


class DefaultScorer:
    """Scorer: (unknowns, boundary_penalty, length_penalty, content_count).

    - ``unknowns``: number of above-level content words in the fragment.
    - ``boundary_penalty``: number of critical dependency arcs that cross
      the fragment boundary (head outside left + children outside right).
    - ``length_penalty``: 0 if content count <= hard cap, otherwise overflow.
    - ``content_count``: tiebreaker preferring shorter fragments.
    """

    def __init__(
        self,
        config: ScoringConfig,
        unknown_counter: UnknownCounter,
    ) -> None:
        self._config = config
        self._unknown_counter = unknown_counter

    def score(
        self,
        indices: Sequence[int],
        tokens: list[TokenData],
    ) -> tuple[int, int, int, int]:
        unknowns = self._unknown_counter(indices, tokens)
        boundary = self._boundary_penalty(indices, tokens)
        content_count = count_content_words(tokens, indices)
        length_penalty = max(
            0, content_count - self._config.length_hard_cap_content_words
        )
        return (
            self._config.weight_unknown * unknowns,
            self._config.weight_boundary_penalty * boundary,
            self._config.weight_length_penalty * length_penalty,
            self._config.weight_content_count * content_count,
        )

    def _boundary_penalty(
        self, indices: Sequence[int], tokens: list[TokenData]
    ) -> int:
        index_set = set(indices)
        if not index_set:
            return 0
        min_idx = min(index_set)
        max_idx = max(index_set)
        critical = self._config.critical_deps
        penalty = 0

        # Left: tokens inside whose head is outside-left with critical dep.
        for idx in index_set:
            head = tokens[idx].head_index
            if head != idx and head < min_idx and tokens[idx].dep in critical:
                penalty += 1

        # Right: children of inside tokens that are outside-right with critical dep.
        for idx in index_set:
            for child_idx in tokens[idx].children_indices:
                if (
                    child_idx > max_idx
                    and not tokens[child_idx].is_punct
                    and tokens[child_idx].dep in critical
                ):
                    penalty += 1

        return penalty
