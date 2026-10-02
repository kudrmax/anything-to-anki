"""Candidate scoring for fragment selection.

The unknown count is supplied via an ``UnknownCounter`` callable so the
domain stays free of CEFR/use-case concerns.
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.fragment_selection.utils import count_content_words

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.value_objects.fragment_selection_config import ScoringConfig


type UnknownCounter = Callable[[Sequence[int], list["TokenData"]], int]


@dataclass(frozen=True, order=True)
class FragmentScore:
    """Lower is better; fields are compared in declaration order.

    - ``length_overflow``: content words above the hard cap — an overlong
      sentence loses even to a cut piece of it.
    - ``incomplete``: 1 if the fragment is not a whole clause. A complete
      phrase beats one with fewer unknown words: the selector must not cut a
      sentence just to drop a second unknown word.
    - ``boundary_penalty``: critical dependency arcs crossing the boundary.
    - ``unknowns``: words besides the target the user probably does not know.
    - ``content_count``: tiebreaker preferring shorter fragments.
    """

    length_overflow: int
    incomplete: int
    boundary_penalty: int
    unknowns: int
    content_count: int


_WORST = sys.maxsize
WORST_FRAGMENT_SCORE = FragmentScore(
    length_overflow=_WORST, incomplete=1, boundary_penalty=_WORST, unknowns=_WORST,
    content_count=_WORST,
)


class Scorer(Protocol):
    """Protocol for candidate scoring. Lower score is better."""

    def score(
        self, indices: Sequence[int], tokens: list[TokenData]
    ) -> FragmentScore:
        ...


class DefaultScorer:
    """Scores a fragment by length, completeness, boundary, unknowns, size."""

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
    ) -> FragmentScore:
        content_count = count_content_words(tokens, indices)
        length_overflow = max(
            0, content_count - self._config.length_hard_cap_content_words
        )
        return FragmentScore(
            length_overflow=self._config.weight_length_penalty * length_overflow,
            incomplete=self._config.weight_incomplete * int(
                not self._is_complete_clause(indices, tokens)
            ),
            boundary_penalty=self._config.weight_boundary_penalty
            * self._boundary_penalty(indices, tokens),
            unknowns=self._config.weight_unknown
            * self._unknown_counter(indices, tokens),
            content_count=self._config.weight_content_count * content_count,
        )

    def _is_complete_clause(
        self, indices: Sequence[int], tokens: list[TokenData]
    ) -> bool:
        """A whole sentence, or a verb with its own subject, that reads as a
        whole phrase:

        - no meaningful word is cut off from any word of the fragment, except
          whole attached clauses ("..., but please trust me");
        - nothing meaningful from another clause is glued on.

        Edge cleanup drops only function words and punctuation, so those
        never make a fragment incomplete.
        """
        index_set = set(indices)
        if any(self._cuts_off_content(idx, index_set, tokens) for idx in index_set):
            return False
        roots = [
            idx for idx in index_set
            if tokens[idx].head_index == idx or tokens[idx].head_index not in index_set
        ]
        clause_roots = [r for r in roots if self._is_clause_head(r, index_set, tokens)]
        if not clause_roots:
            return False
        return all(
            not self._carries_content(r, index_set, tokens)
            for r in roots
            if r not in clause_roots
        )

    def _is_clause_head(
        self, idx: int, index_set: set[int], tokens: list[TokenData]
    ) -> bool:
        token = tokens[idx]
        if token.head_index == idx:
            return True
        return token.pos in self._config.clause_head_pos and any(
            child in index_set and tokens[child].dep in self._config.clause_subject_deps
            for child in token.children_indices
        )

    def _cuts_off_content(
        self, idx: int, index_set: set[int], tokens: list[TokenData]
    ) -> bool:
        return any(
            child not in index_set
            and tokens[child].sent_index == tokens[idx].sent_index
            and tokens[child].dep not in self._config.detachable_clause_deps
            and _subtree_has_content(child, tokens, within=None)
            for child in tokens[idx].children_indices
        )

    @staticmethod
    def _carries_content(
        root: int, index_set: set[int], tokens: list[TokenData]
    ) -> bool:
        return _subtree_has_content(root, tokens, within=index_set)

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


def _subtree_has_content(
    root: int, tokens: list[TokenData], within: set[int] | None,
) -> bool:
    """Whether the subtree of ``root`` (limited to ``within`` when given)
    has a meaningful word — alphabetic and not a stop word."""
    sent_index = tokens[root].sent_index
    stack = [root]
    seen: set[int] = set()
    while stack:
        idx = stack.pop()
        if idx in seen or tokens[idx].sent_index != sent_index:
            continue
        if within is not None and idx not in within:
            continue
        seen.add(idx)
        if tokens[idx].is_alpha and not tokens[idx].is_stop:
            return True
        stack.extend(tokens[idx].children_indices)
    return False
