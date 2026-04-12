from __future__ import annotations

from abc import ABC, abstractmethod


class PhrasalVerbDictionary(ABC):
    """Port for checking if a verb+particle combination is a known phrasal verb."""

    @abstractmethod
    def contains(self, verb_lemma: str, particle: str) -> bool:
        """Return True if 'verb_lemma particle' is a known phrasal verb."""
        ...

    def contains_phrase(self, phrase: str) -> bool:
        """Return True if the full phrase is a known phrasal verb.

        Default implementation splits into verb + rest and delegates to contains().
        Subclasses may override for direct lookup.
        """
        parts = phrase.strip().split(None, 1)
        if len(parts) != 2:
            return False
        return self.contains(parts[0], parts[1])
