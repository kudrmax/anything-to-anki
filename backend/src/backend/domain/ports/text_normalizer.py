from __future__ import annotations

from abc import ABC, abstractmethod


class TextNormalizer(ABC):
    """Port for normalizing informal text before NLP analysis (layer 2.5)."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Expand informal contractions and slang into standard English."""
