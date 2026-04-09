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
    ) -> tuple[int, int, int]:
        ...


class DefaultScorer:
    """Default scorer: (weight_unknown * unknowns, length_penalty, content_count).

    - ``unknowns``: number of above-level content words in the fragment,
      supplied by the injected ``UnknownCounter``.
    - ``length_penalty``: 0 if content count <= hard cap, otherwise the overflow.
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
    ) -> tuple[int, int, int]:
        unknowns = self._unknown_counter(indices, tokens)
        content_count = count_content_words(tokens, indices)
        length_penalty = max(
            0, content_count - self._config.length_hard_cap_content_words
        )
        return (
            self._config.weight_unknown * unknowns,
            self._config.weight_length_penalty * length_penalty,
            self._config.weight_content_count * content_count,
        )
