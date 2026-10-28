from __future__ import annotations

from abc import ABC, abstractmethod


class StopWords(ABC):
    """Port for the function words that are never worth a card: "to", "have", "will"."""

    @abstractmethod
    def contains(self, lemma: str) -> bool:
        """Return True if the word is a function word."""
        ...
