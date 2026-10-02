from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordDecision:
    """The user's latest verdict on a word: known or to learn.

    Kept apart from candidates so it survives deleting the source.
    """

    lemma: str
    zipf_frequency: float
    is_known: bool
