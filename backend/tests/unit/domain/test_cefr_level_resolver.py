from __future__ import annotations

from backend.domain.services.cefr_level_resolver import resolve_cefr_level
from backend.domain.value_objects.cefr_breakdown import SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


def _vote(name: str, level: CEFRLevel) -> SourceVote:
    return SourceVote(source_name=name, distribution={level: 1.0}, top_level=level)


def _unknown(name: str) -> SourceVote:
    return _vote(name, CEFRLevel.UNKNOWN)


class TestBothPrioritySources:
    def test_takes_lower_when_both_known(self) -> None:
        votes = [
            _vote("Oxford 5000", CEFRLevel.B2),
            _vote("Cambridge Dictionary", CEFRLevel.C1),
            _vote("CEFRpy", CEFRLevel.A2),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.B2
        assert method == "priority"

    def test_takes_lower_cambridge_wins(self) -> None:
        votes = [
            _vote("Oxford 5000", CEFRLevel.C1),
            _vote("Cambridge Dictionary", CEFRLevel.A2),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.A2
        assert method == "priority"

    def test_same_level_both_known(self) -> None:
        votes = [
            _vote("Oxford 5000", CEFRLevel.B1),
            _vote("Cambridge Dictionary", CEFRLevel.B1),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.B1
        assert method == "priority"


class TestOnePrioritySource:
    def test_oxford_only(self) -> None:
        votes = [
            _vote("Oxford 5000", CEFRLevel.B2),
            _unknown("Cambridge Dictionary"),
            _vote("CEFRpy", CEFRLevel.C2),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.B2
        assert method == "priority"

    def test_cambridge_only(self) -> None:
        votes = [
            _unknown("Oxford 5000"),
            _vote("Cambridge Dictionary", CEFRLevel.B1),
            _vote("CEFRpy", CEFRLevel.C2),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.B1
        assert method == "priority"

    def test_oxford_alone_in_list(self) -> None:
        votes = [_vote("Oxford 5000", CEFRLevel.A1)]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.A1
        assert method == "priority"

    def test_cambridge_alone_unknown(self) -> None:
        votes = [_unknown("Cambridge Dictionary")]
        level, _ = resolve_cefr_level(votes)
        assert level == CEFRLevel.UNKNOWN


class TestVotingFallback:
    def test_voting_when_both_unknown(self) -> None:
        votes = [
            _unknown("Oxford 5000"),
            _unknown("Cambridge Dictionary"),
            _vote("CEFRpy", CEFRLevel.A2),
            _vote("Kelly List", CEFRLevel.A2),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.A2
        assert method == "voting"

    def test_equal_weight_majority(self) -> None:
        votes = [
            _unknown("Oxford 5000"),
            _unknown("Cambridge Dictionary"),
            _vote("CEFRpy", CEFRLevel.B1),
            _vote("EFLLex", CEFRLevel.B1),
            _vote("Kelly List", CEFRLevel.C1),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.B1
        assert method == "voting"

    def test_tie_prefers_lower_level(self) -> None:
        votes = [
            _unknown("Oxford 5000"),
            _unknown("Cambridge Dictionary"),
            _vote("CEFRpy", CEFRLevel.A2),
            _vote("Kelly List", CEFRLevel.B1),
        ]
        level, _ = resolve_cefr_level(votes)
        assert level == CEFRLevel.A2

    def test_all_unknown(self) -> None:
        votes = [
            _unknown("Oxford 5000"),
            _unknown("Cambridge Dictionary"),
            _unknown("CEFRpy"),
            _unknown("Kelly List"),
        ]
        level, method = resolve_cefr_level(votes)
        assert level == CEFRLevel.UNKNOWN
        assert method == "voting"

    def test_no_votes_at_all(self) -> None:
        level, method = resolve_cefr_level([])
        assert level == CEFRLevel.UNKNOWN
        assert method == "voting"

    def test_distributed_source(self) -> None:
        efllex = SourceVote(
            source_name="EFLLex",
            distribution={CEFRLevel.A2: 0.7, CEFRLevel.B1: 0.3},
            top_level=CEFRLevel.A2,
        )
        votes = [
            _unknown("Oxford 5000"),
            _unknown("Cambridge Dictionary"),
            efllex,
            _vote("CEFRpy", CEFRLevel.B1),
            _vote("Kelly List", CEFRLevel.B1),
        ]
        level, _ = resolve_cefr_level(votes)
        # EFLLex: A2=0.7/3, B1=0.3/3; CEFRpy: B1=1/3; Kelly: B1=1/3
        # B1 total = 0.1 + 0.333 + 0.333 = 0.766; A2 = 0.233
        assert level == CEFRLevel.B1
