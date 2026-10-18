from __future__ import annotations

from abc import ABC, abstractmethod


class LearningQuery(ABC):
    """Port for the lemmas the user is learning ("учу"), lowercase."""

    @abstractmethod
    def awaiting_export(self) -> frozenset[str]:
        """Words marked Learn in any source and not exported yet."""

    @abstractmethod
    def in_anki(self) -> frozenset[str]:
        """Lemmas of every note exported to Anki."""

    def learning_lemmas(self) -> frozenset[str]:
        return self.awaiting_export() | self.in_anki()
