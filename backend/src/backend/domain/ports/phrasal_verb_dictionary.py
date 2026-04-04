from __future__ import annotations

from abc import ABC, abstractmethod


class PhrasalVerbDictionary(ABC):
    """Port for checking if a verb+particle combination is a known phrasal verb."""

    @abstractmethod
    def contains(self, verb_lemma: str, particle: str) -> bool:
        """Return True if 'verb_lemma particle' is a known phrasal verb."""
        ...
