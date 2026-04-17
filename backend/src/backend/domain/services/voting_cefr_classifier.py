from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
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
        return self.classify_detailed(lemma, pos_tag).final_level

    def classify_detailed(self, lemma: str, pos_tag: str) -> CEFRBreakdown:
        priority_vote: SourceVote | None = None

        if self._priority_source is not None:
            priority_vote = self._build_vote(self._priority_source, lemma, pos_tag)

        votes = [self._build_vote(s, lemma, pos_tag) for s in self._sources]

        # Priority path: if priority source knows the word, use its answer
        if priority_vote is not None and priority_vote.top_level is not CEFRLevel.UNKNOWN:
            return CEFRBreakdown(
                final_level=priority_vote.top_level,
                decision_method="priority",
                priority_vote=priority_vote,
                votes=votes,
            )

        # Voting path
        final_level = self._compute_voting_result(votes)
        return CEFRBreakdown(
            final_level=final_level,
            decision_method="voting",
            priority_vote=priority_vote,
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

    def _compute_voting_result(self, votes: list[SourceVote]) -> CEFRLevel:
        weight = 1.0 / len(votes)
        totals: dict[CEFRLevel, float] = defaultdict(float)
        for vote in votes:
            for level, prob in vote.distribution.items():
                totals[level] += prob * weight
        # Pick level with highest probability; on tie prefer lower level (lower .value)
        return max(totals, key=lambda lvl: (totals[lvl], -lvl.value))
