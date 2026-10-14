from __future__ import annotations

from abc import ABC, abstractmethod


class LearningQuery(ABC):
    """Port for the lemmas the user is learning ("учу")."""

    @abstractmethod
    def learning_lemmas(self) -> frozenset[str]:
        """Lowercase lemmas of words marked Learn in any source and not exported yet."""
