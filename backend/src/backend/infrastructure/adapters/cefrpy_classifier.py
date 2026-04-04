from __future__ import annotations

from cefrpy import CEFRAnalyzer

from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel


class CefrpyCEFRClassifier(CEFRClassifier):
    """Classifies words by CEFR level using the cefrpy library."""

    def __init__(self) -> None:
        self._analyzer = CEFRAnalyzer()

    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        # Try exact match with POS tag first
        level = self._analyzer.get_word_pos_level_float(lemma.lower(), pos_tag)
        if level is not None and level > 0:
            return CEFRLevel.from_float(level)

        # Fallback: average across all POS tags
        level = self._analyzer.get_average_word_level_float(lemma.lower())
        if level is not None and level > 0:
            return CEFRLevel.from_float(level)

        return CEFRLevel.UNKNOWN
