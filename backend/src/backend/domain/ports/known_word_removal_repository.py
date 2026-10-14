from __future__ import annotations

from abc import ABC, abstractmethod


class KnownWordRemovalRepository(ABC):
    """Port for the lemmas the user took out of Known: Anki maturity never puts them back."""

    @abstractmethod
    def add(self, lemma: str) -> None: ...

    @abstractmethod
    def discard(self, lemma: str) -> None:
        """The user marked the lemma Known again."""

    @abstractmethod
    def contains(self, lemma: str) -> bool: ...
