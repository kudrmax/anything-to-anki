from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.services.cefr_level_resolver import resolve_cefr_level
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.ports.cefr_source import CEFRSource


class VotingCEFRClassifier(CEFRClassifier):
    """Classifies words using priority sources and weighted voting.

    Accepts a list of priority sources checked in order.  The first
    priority source that returns a known level wins.  If none do,
    falls back to equal-weight voting among the remaining sources.

    Resolution logic is delegated to ``resolve_cefr_level``.
    """

    def __init__(
        self,
        sources: list[CEFRSource],
        priority_sources: list[CEFRSource] | None = None,
    ) -> None:
        if not sources:
            raise ValueError("At least one CEFRSource is required")
        self._sources = sources
        self._priority_sources = priority_sources or []

    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        return self.classify_detailed(lemma, pos_tag).final_level

    def classify_detailed(self, lemma: str, pos_tag: str) -> CEFRBreakdown:
        priority_votes = [
            self._build_vote(s, lemma, pos_tag) for s in self._priority_sources
        ]
        votes = [self._build_vote(s, lemma, pos_tag) for s in self._sources]

        all_votes = [*priority_votes, *votes]
        final_level, decision_method = resolve_cefr_level(all_votes)

        return CEFRBreakdown(
            final_level=final_level,
            decision_method=decision_method,
            priority_votes=priority_votes,
            votes=votes,
        )

    def _build_vote(self, source: CEFRSource, lemma: str, pos_tag: str) -> SourceVote:
        distribution = source.get_distribution(lemma, pos_tag)
        top_level = max(distribution, key=lambda lvl: distribution[lvl])
        return SourceVote(
            source_name=source.name,
            distribution=distribution,
            top_level=top_level,
        )
