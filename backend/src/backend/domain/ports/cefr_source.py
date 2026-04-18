from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_level import CEFRLevel


class CEFRSource(ABC):
    """Port for a single CEFR level data source.

    Each source returns a probability distribution over CEFR levels.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this CEFR data source."""

    @abstractmethod
    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        """Return probability distribution across CEFR levels for a word.

        Values must sum to 1.0.
        If the word is not in this source, return {CEFRLevel.UNKNOWN: 1.0}.
        """
