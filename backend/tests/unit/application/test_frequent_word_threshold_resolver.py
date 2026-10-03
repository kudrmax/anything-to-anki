from unittest.mock import MagicMock

import pytest
from backend.domain.entities.word_decision import WordDecision

from tests.candidate_sorter_support import threshold_resolver


def _settings(value: str | None) -> MagicMock:
    repo = MagicMock()
    repo.get.side_effect = lambda key, default=None: (
        value if key == "frequent_word_threshold" else default
    )
    return repo


def _friends_pilot() -> list[WordDecision]:
    known = [WordDecision(f"k{i}", 4.2, True) for i in range(9)]
    known += [WordDecision(f"m{i}", 3.7, True) for i in range(6)]
    learn = [WordDecision(f"l{i}", 4.2, False) for i in range(2)]
    learn += [WordDecision(f"n{i}", 3.7, False) for i in range(2)]
    return known + learn


@pytest.mark.unit
class TestFrequentWordThresholdResolver:
    def test_auto_is_calibrated_on_decisions(self) -> None:
        resolved = threshold_resolver(_settings("auto"), _friends_pilot()).resolve()
        assert resolved.is_auto
        assert resolved.zipf == 3.5

    def test_auto_without_decisions_falls_back(self) -> None:
        assert threshold_resolver(_settings("auto")).resolve().zipf == 4.5

    def test_fixed_value_ignores_decisions(self) -> None:
        assert threshold_resolver(_settings("5.0"), _friends_pilot()).resolve().zipf == 5.0

    def test_off(self) -> None:
        assert threshold_resolver(_settings("off"), _friends_pilot()).resolve().zipf is None

    def test_missing_or_broken_setting_means_auto(self) -> None:
        assert threshold_resolver(_settings(None), _friends_pilot()).resolve().zipf == 3.5
        assert threshold_resolver(_settings("3.0"), _friends_pilot()).resolve().zipf == 3.5
