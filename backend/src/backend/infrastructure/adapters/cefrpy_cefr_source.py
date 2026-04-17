from __future__ import annotations

from cefrpy import CEFRAnalyzer

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel


class CefrpyCEFRSource(CEFRSource):
    """CEFR source backed by the cefrpy library."""

    def __init__(self) -> None:
        self._analyzer = CEFRAnalyzer()

    @property
    def name(self) -> str:
        return "CEFRpy"

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        lower = lemma.lower()

        # Try exact match with POS tag first
        level = self._analyzer.get_word_pos_level_float(lower, pos_tag)
        if level is not None and level > 0:
            return {CEFRLevel.from_float(level): 1.0}

        # Fallback: average across all POS tags
        level = self._analyzer.get_average_word_level_float(lower)
        if level is not None and level > 0:
            return {CEFRLevel.from_float(level): 1.0}

        return {CEFRLevel.UNKNOWN: 1.0}
