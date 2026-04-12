from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from backend.domain.ports.cefr_classifier import CEFRClassifier

if TYPE_CHECKING:
    from backend.domain.ports.cefr_source import CEFRSource
    from backend.domain.value_objects.cefr_level import CEFRLevel


class VotingCEFRClassifier(CEFRClassifier):
    """Classifies words by averaging CEFR distributions from multiple sources."""

    def __init__(self, sources: list[CEFRSource]) -> None:
        if not sources:
            raise ValueError("At least one CEFRSource is required")
        self._sources = sources

    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        weight = 1.0 / len(self._sources)
        totals: dict[CEFRLevel, float] = defaultdict(float)

        for source in self._sources:
            distribution = source.get_distribution(lemma, pos_tag)
            for level, prob in distribution.items():
                totals[level] += prob * weight

        # Pick level with highest probability; on tie prefer lower level (lower .value)
        return max(
            totals,
            key=lambda lvl: (totals[lvl], -lvl.value),
        )
