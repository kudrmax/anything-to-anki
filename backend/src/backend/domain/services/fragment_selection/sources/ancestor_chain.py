"""Ancestor chain candidate source — walks target's head, head.head, ..."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.candidate import Candidate
from backend.domain.services.fragment_selection.utils import (
    collect_subtree_in_sentence,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData


class AncestorChainSource:
    """Yields the subtree rooted at the target, then at its head, at its
    head's head, and so on up to the sentence root."""

    name: str = "ancestor_chain"

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        sent_index = tokens[target_index].sent_index
        seen_roots: set[int] = set()
        cursor = target_index
        while cursor not in seen_roots:
            seen_roots.add(cursor)
            subtree = collect_subtree_in_sentence(tokens, cursor, sent_index)
            if subtree and target_index in subtree:
                yield Candidate(
                    indices=tuple(sorted(subtree)),
                    source_name=self.name,
                )
            head = tokens[cursor].head_index
            if head == cursor:
                break
            cursor = head
