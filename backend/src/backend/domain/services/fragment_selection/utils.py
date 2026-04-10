"""Shared helpers for the fragment selection pipeline."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData


def count_content_words(
    tokens: list[TokenData], indices: Iterable[int]
) -> int:
    """Count alphabetic, non-punctuation tokens at the given indices."""
    return sum(
        1
        for idx in indices
        if tokens[idx].is_alpha and not tokens[idx].is_punct
    )


def collect_subtree_in_sentence(
    tokens: list[TokenData], root_index: int, sent_index: int
) -> set[int]:
    """Collect the dependency subtree rooted at ``root_index``, staying
    inside the sentence identified by ``sent_index``."""
    result: set[int] = set()
    stack = [root_index]
    while stack:
        idx = stack.pop()
        if idx in result:
            continue
        if tokens[idx].sent_index != sent_index:
            continue
        result.add(idx)
        stack.extend(tokens[idx].children_indices)
    return result
