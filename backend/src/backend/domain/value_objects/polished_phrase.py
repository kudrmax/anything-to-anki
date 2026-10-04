from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolishedPhrase:
    """AI's easier version of one phrase from a batch, matched by its 1-based index."""

    phrase_index: int
    phrase: str
