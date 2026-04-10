"""Whitespace-preserving rendering of token index lists."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData


def render_fragment(tokens: list[TokenData], indices: Iterable[int]) -> str:
    """Render tokens at ``indices`` as text, preserving original whitespace."""
    sorted_indices = sorted(indices)
    if not sorted_indices:
        return ""
    parts = [tokens[i].text + tokens[i].whitespace_after for i in sorted_indices]
    return "".join(parts).strip()
