from __future__ import annotations

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel


class StubSource(CEFRSource):
    """Test stub that returns a fixed distribution."""

    def __init__(self, distribution: dict[CEFRLevel, float], name: str = "stub") -> None:
        self._distribution = distribution
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        return self._distribution


class TestVotingCEFRClassifier:
    def test_all_sources_agree(self) -> None:
        sources = [
            StubSource({CEFRLevel.B1: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.B1

    def test_majority_wins(self) -> None:
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_distributed_source_contributes_proportionally(self) -> None:
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.A2: 0.6, CEFRLevel.B1: 0.3, CEFRLevel.B2: 0.1}),
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        # A2: 0.25 + 0.25*0.6 + 0.25 = 0.65
        # B1: 0.25*0.3 + 0.25 = 0.325
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_unknown_wins_when_most_sources_dont_know(self) -> None:
        sources = [
            StubSource({CEFRLevel.C2: 1.0}),
            StubSource({CEFRLevel.UNKNOWN: 1.0}),
            StubSource({CEFRLevel.UNKNOWN: 1.0}),
            StubSource({CEFRLevel.UNKNOWN: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.UNKNOWN

    def test_all_unknown(self) -> None:
        sources = [
            StubSource({CEFRLevel.UNKNOWN: 1.0}),
            StubSource({CEFRLevel.UNKNOWN: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.UNKNOWN

    def test_tie_returns_lower_level(self) -> None:
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        # A2: 50%, B1: 50% — tie, prefer lower
        assert classifier.classify("word", "NN") == CEFRLevel.A2


class TestVotingCEFRClassifierPrioritySource:
    def test_priority_source_overrides_voting(self) -> None:
        """When priority source returns a known level, voting is skipped."""
        priority = StubSource({CEFRLevel.A2: 1.0})
        sources = [
            StubSource({CEFRLevel.C2: 1.0}),
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_source=priority)
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_priority_source_unknown_falls_back_to_voting(self) -> None:
        """When priority source returns UNKNOWN, voting proceeds normally."""
        priority = StubSource({CEFRLevel.UNKNOWN: 1.0})
        sources = [
            StubSource({CEFRLevel.B1: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_source=priority)
        assert classifier.classify("word", "NN") == CEFRLevel.B1

    def test_no_priority_source_works_as_before(self) -> None:
        """Without priority_source, classifier works exactly like before."""
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_priority_source_not_in_voting_pool(self) -> None:
        """Priority source does not participate in fallback voting."""
        priority = StubSource({CEFRLevel.UNKNOWN: 1.0})
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_source=priority)
        assert classifier.classify("word", "NN") == CEFRLevel.A2
