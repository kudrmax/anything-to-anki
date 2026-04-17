from __future__ import annotations

from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


class TestSourceVote:
    def test_frozen(self) -> None:
        vote = SourceVote(
            source_name="test",
            distribution={CEFRLevel.B1: 1.0},
            top_level=CEFRLevel.B1,
        )
        assert vote.source_name == "test"
        assert vote.top_level == CEFRLevel.B1

    def test_distribution_preserved(self) -> None:
        dist = {CEFRLevel.A2: 0.6, CEFRLevel.B1: 0.4}
        vote = SourceVote(source_name="src", distribution=dist, top_level=CEFRLevel.A2)
        assert vote.distribution == dist


class TestCEFRBreakdown:
    def test_priority_breakdown(self) -> None:
        priority = SourceVote(
            source_name="Cambridge",
            distribution={CEFRLevel.B1: 1.0},
            top_level=CEFRLevel.B1,
        )
        breakdown = CEFRBreakdown(
            final_level=CEFRLevel.B1,
            decision_method="priority",
            priority_vote=priority,
            votes=[],
        )
        assert breakdown.decision_method == "priority"
        assert breakdown.priority_vote is not None
        assert breakdown.final_level == CEFRLevel.B1

    def test_voting_breakdown(self) -> None:
        votes = [
            SourceVote("src1", {CEFRLevel.A2: 1.0}, CEFRLevel.A2),
            SourceVote("src2", {CEFRLevel.B1: 1.0}, CEFRLevel.B1),
        ]
        breakdown = CEFRBreakdown(
            final_level=CEFRLevel.A2,
            decision_method="voting",
            priority_vote=None,
            votes=votes,
        )
        assert breakdown.decision_method == "voting"
        assert breakdown.priority_vote is None
        assert len(breakdown.votes) == 2
