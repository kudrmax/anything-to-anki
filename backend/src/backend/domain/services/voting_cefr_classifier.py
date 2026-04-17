from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.ports.cefr_source import CEFRSource


class VotingCEFRClassifier(CEFRClassifier):
    """Classifies words by averaging CEFR distributions from multiple sources.

    Optionally accepts a priority_source. If the priority source returns
    a known level (not UNKNOWN), that level is used directly and voting
    is skipped. Otherwise, falls back to equal-weight voting.
    """

    def __init__(
        self,
        sources: list[CEFRSource],
        priority_source: CEFRSource | None = None,
    ) -> None:
        if not sources:
            raise ValueError("At least one CEFRSource is required")
        self._sources = sources
        self._priority_source = priority_source

    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        if self._priority_source is not None:
            distribution = self._priority_source.get_distribution(lemma, pos_tag)
            level = max(distribution, key=lambda lvl: distribution[lvl])
            if level is not CEFRLevel.UNKNOWN:
                return level

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
