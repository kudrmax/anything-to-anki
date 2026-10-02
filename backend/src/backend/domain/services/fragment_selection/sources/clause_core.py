"""Clause core candidate source — a clause without the clauses attached to it."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.candidate import Candidate
from backend.domain.value_objects.fragment_selection_config import (
    CLAUSE_HEAD_POS,
    DETACHABLE_CLAUSE_DEPS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData


class ClauseCoreSource:
    """Yields, for every verb and the root of the target's sentence, its
    subtree without attached clauses ("I can't win arguments with you" out
    of "I can't win arguments with you, but please, trust me"), cut down to
    the gap-free piece around the target."""

    name: str = "clause_core"

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        sent_index = tokens[target_index].sent_index
        for token in tokens:
            if token.sent_index != sent_index:
                continue
            is_root = token.head_index == token.index
            if not is_root and token.pos not in CLAUSE_HEAD_POS:
                continue
            core = self._core(tokens, token.index, sent_index)
            if target_index in core:
                yield Candidate(
                    indices=self._run_around(core, target_index), source_name=self.name,
                )

    @staticmethod
    def _run_around(indices: set[int], target_index: int) -> tuple[int, ...]:
        """The gap-free run of indices containing the target: a clause cut
        out of the middle must not glue its neighbours together."""
        start = target_index
        while start - 1 in indices:
            start -= 1
        end = target_index
        while end + 1 in indices:
            end += 1
        return tuple(range(start, end + 1))

    @staticmethod
    def _core(tokens: list[TokenData], head: int, sent_index: int) -> set[int]:
        result: set[int] = set()
        stack = [head]
        while stack:
            idx = stack.pop()
            if idx in result or tokens[idx].sent_index != sent_index:
                continue
            result.add(idx)
            stack.extend(
                child for child in tokens[idx].children_indices
                if tokens[child].dep not in DETACHABLE_CLAUSE_DEPS
            )
        return result
