from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.value_objects.cefr_level import CEFRLevel


class CEFRSource(ABC):
    """Port for a single CEFR level data source.

    Each source returns a probability distribution over CEFR levels.
    """

    @abstractmethod
    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        """Return probability distribution across CEFR levels for a word.

        Values must sum to 1.0.
        If the word is not in this source, return {CEFRLevel.UNKNOWN: 1.0}.
        """
