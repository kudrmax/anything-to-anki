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


class TestPrioritySources:
    def test_first_priority_overrides_voting(self) -> None:
        """When first priority source returns a known level, voting is skipped."""
        priority = StubSource({CEFRLevel.A2: 1.0}, name="Oxford 5000")
        sources = [
            StubSource({CEFRLevel.C2: 1.0}),
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_sources=[priority])
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_second_priority_when_first_unknown(self) -> None:
        """Second priority source wins when first returns UNKNOWN."""
        oxford = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Oxford 5000")
        cambridge = StubSource({CEFRLevel.B1: 1.0}, name="Cambridge Dictionary")
        sources = [
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_sources=[oxford, cambridge])
        assert classifier.classify("word", "NN") == CEFRLevel.B1

    def test_all_priority_unknown_falls_back_to_voting(self) -> None:
        """When all priority sources return UNKNOWN, voting proceeds normally."""
        oxford = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Oxford 5000")
        cambridge = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Cambridge Dictionary")
        sources = [
            StubSource({CEFRLevel.B1: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(
            sources, priority_sources=[oxford, cambridge],
        )
        assert classifier.classify("word", "NN") == CEFRLevel.B1

    def test_no_priority_sources_works(self) -> None:
        """Without priority_sources, classifier uses pure voting."""
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.B1: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources)
        assert classifier.classify("word", "NN") == CEFRLevel.A2

    def test_priority_sources_not_in_voting_pool(self) -> None:
        """Priority sources do not participate in fallback voting."""
        oxford = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Oxford 5000")
        sources = [
            StubSource({CEFRLevel.A2: 1.0}),
            StubSource({CEFRLevel.C2: 1.0}),
        ]
        classifier = VotingCEFRClassifier(sources, priority_sources=[oxford])
        assert classifier.classify("word", "NN") == CEFRLevel.A2


class TestClassifyDetailed:
    def test_priority_decides(self) -> None:
        oxford = StubSource({CEFRLevel.A2: 1.0}, name="Oxford 5000")
        cambridge = StubSource({CEFRLevel.C1: 1.0}, name="Cambridge Dictionary")
        sources = [
            StubSource({CEFRLevel.C2: 1.0}, name="Src1"),
            StubSource({CEFRLevel.C2: 1.0}, name="Src2"),
        ]
        classifier = VotingCEFRClassifier(
            sources, priority_sources=[oxford, cambridge],
        )
        breakdown = classifier.classify_detailed("word", "NN")

        assert breakdown.final_level == CEFRLevel.A2
        assert breakdown.decision_method == "priority"
        assert len(breakdown.priority_votes) == 2
        assert breakdown.priority_votes[0].source_name == "Oxford 5000"
        assert len(breakdown.votes) == 2

    def test_priority_unknown_falls_to_voting(self) -> None:
        oxford = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Oxford 5000")
        cambridge = StubSource({CEFRLevel.UNKNOWN: 1.0}, name="Cambridge Dictionary")
        sources = [
            StubSource({CEFRLevel.B1: 1.0}, name="Src1"),
            StubSource({CEFRLevel.B1: 1.0}, name="Src2"),
        ]
        classifier = VotingCEFRClassifier(
            sources, priority_sources=[oxford, cambridge],
        )
        breakdown = classifier.classify_detailed("word", "NN")

        assert breakdown.final_level == CEFRLevel.B1
        assert breakdown.decision_method == "voting"
        assert len(breakdown.priority_votes) == 2
        assert breakdown.priority_votes[0].top_level == CEFRLevel.UNKNOWN

    def test_no_priority_sources(self) -> None:
        sources = [
            StubSource({CEFRLevel.A2: 1.0}, name="Src1"),
            StubSource({CEFRLevel.B1: 1.0}, name="Src2"),
        ]
        classifier = VotingCEFRClassifier(sources)
        breakdown = classifier.classify_detailed("word", "NN")

        assert breakdown.final_level == CEFRLevel.A2  # tie -> lower
        assert breakdown.decision_method == "voting"
        assert breakdown.priority_votes == []

    def test_consistency_with_classify(self) -> None:
        """classify_detailed().final_level must always equal classify()."""
        oxford = StubSource({CEFRLevel.B2: 1.0}, name="Oxford 5000")
        sources = [
            StubSource({CEFRLevel.A2: 1.0}, name="Src1"),
            StubSource({CEFRLevel.C1: 1.0}, name="Src2"),
        ]
        classifier = VotingCEFRClassifier(sources, priority_sources=[oxford])

        assert classifier.classify("word", "NN") == classifier.classify_detailed("word", "NN").final_level

    def test_source_names_in_votes(self) -> None:
        sources = [
            StubSource({CEFRLevel.A2: 1.0}, name="Source A"),
            StubSource({CEFRLevel.B1: 1.0}, name="Source B"),
        ]
        classifier = VotingCEFRClassifier(sources)
        breakdown = classifier.classify_detailed("word", "NN")

        names = [v.source_name for v in breakdown.votes]
        assert names == ["Source A", "Source B"]

    def test_votes_contain_all_sources_even_when_priority_decides(self) -> None:
        oxford = StubSource({CEFRLevel.A1: 1.0}, name="Oxford 5000")
        sources = [
            StubSource({CEFRLevel.B1: 1.0}, name="S1"),
            StubSource({CEFRLevel.B2: 1.0}, name="S2"),
            StubSource({CEFRLevel.C1: 1.0}, name="S3"),
        ]
        classifier = VotingCEFRClassifier(sources, priority_sources=[oxford])
        breakdown = classifier.classify_detailed("word", "NN")

        assert breakdown.decision_method == "priority"
        assert len(breakdown.votes) == 3  # all voting sources still queried
