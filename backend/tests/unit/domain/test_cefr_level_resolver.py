from __future__ import annotations

from backend.domain.services.cefr_level_resolver import resolve_cefr_level
from backend.domain.value_objects.cefr_breakdown import SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


def _vote(name: str, level: CEFRLevel) -> SourceVote:
    return SourceVote(source_name=name, distribution={level: 1.0}, top_level=level)


def _unknown(name: str) -> SourceVote:
    return _vote(name, CEFRLevel.UNKNOWN)


class TestPrioritySources:
    def test_takes_lower_when_both_known(self) -> None:
        priority = [
            _vote("Src1", CEFRLevel.B2),
            _vote("Src2", CEFRLevel.C1),
        ]
        regular = [_vote("Src3", CEFRLevel.A2)]
        level, method = resolve_cefr_level(priority, regular)
        assert level == CEFRLevel.B2
        assert method == "priority"

    def test_takes_lower_second_priority_wins(self) -> None:
        priority = [
            _vote("Src1", CEFRLevel.C1),
            _vote("Src2", CEFRLevel.A2),
        ]
        level, method = resolve_cefr_level(priority, [])
        assert level == CEFRLevel.A2
        assert method == "priority"

    def test_same_level_both_known(self) -> None:
        priority = [
            _vote("Src1", CEFRLevel.B1),
            _vote("Src2", CEFRLevel.B1),
        ]
        level, method = resolve_cefr_level(priority, [])
        assert level == CEFRLevel.B1
        assert method == "priority"

    def test_single_priority_known(self) -> None:
        priority = [_vote("Src1", CEFRLevel.B2)]
        regular = [_vote("Src2", CEFRLevel.C2)]
        level, method = resolve_cefr_level(priority, regular)
        assert level == CEFRLevel.B2
        assert method == "priority"

    def test_priority_unknown_falls_to_voting(self) -> None:
        priority = [_unknown("Src1")]
        regular = [_vote("Src2", CEFRLevel.B1)]
        level, method = resolve_cefr_level(priority, regular)
        assert level == CEFRLevel.B1
        assert method == "voting"

    def test_all_priority_unknown(self) -> None:
        priority = [_unknown("Src1"), _unknown("Src2")]
        regular = [_vote("Src3", CEFRLevel.A2)]
        level, method = resolve_cefr_level(priority, regular)
        assert level == CEFRLevel.A2
        assert method == "voting"


class TestVotingFallback:
    def test_no_priority_sources(self) -> None:
        regular = [
            _vote("Src1", CEFRLevel.A2),
            _vote("Src2", CEFRLevel.A2),
        ]
        level, method = resolve_cefr_level([], regular)
        assert level == CEFRLevel.A2
        assert method == "voting"

    def test_equal_weight_majority(self) -> None:
        regular = [
            _vote("Src1", CEFRLevel.B1),
            _vote("Src2", CEFRLevel.B1),
            _vote("Src3", CEFRLevel.C1),
        ]
        level, method = resolve_cefr_level([], regular)
        assert level == CEFRLevel.B1
        assert method == "voting"

    def test_tie_prefers_lower_level(self) -> None:
        regular = [
            _vote("Src1", CEFRLevel.A2),
            _vote("Src2", CEFRLevel.B1),
        ]
        level, _ = resolve_cefr_level([], regular)
        assert level == CEFRLevel.A2

    def test_all_unknown(self) -> None:
        regular = [_unknown("Src1"), _unknown("Src2")]
        level, method = resolve_cefr_level([], regular)
        assert level == CEFRLevel.UNKNOWN
        assert method == "voting"

    def test_empty_lists(self) -> None:
        level, method = resolve_cefr_level([], [])
        assert level == CEFRLevel.UNKNOWN
        assert method == "voting"

    def test_distributed_source(self) -> None:
        efllex = SourceVote(
            source_name="EFLLex",
            distribution={CEFRLevel.A2: 0.7, CEFRLevel.B1: 0.3},
            top_level=CEFRLevel.A2,
        )
        regular = [
            efllex,
            _vote("Src2", CEFRLevel.B1),
            _vote("Src3", CEFRLevel.B1),
        ]
        level, _ = resolve_cefr_level([], regular)
        assert level == CEFRLevel.B1
