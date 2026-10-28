from unittest.mock import MagicMock

import pytest
from backend.domain.entities.word_decision import WordDecision
from backend.domain.value_objects.cefr_level import CEFRLevel

from tests.candidate_sorter_support import threshold_resolver


def _settings(value: str | None, level: str | None = "C1") -> MagicMock:
    saved = {"frequent_word_threshold": value, "cefr_level": level}
    repo = MagicMock()
    repo.get.side_effect = lambda key, default=None: saved.get(key) or default
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

    @pytest.mark.parametrize(
        ("level", "zipf"),
        [("A1", None), ("A2", 5.5), ("B1", 5.5), ("B2", 5.0), ("C1", 4.5), ("C2", 4.0)],
    )
    def test_auto_without_decisions_starts_at_the_level(
        self, level: str, zipf: float | None,
    ) -> None:
        assert threshold_resolver(_settings("auto", level)).resolve().zipf == zipf

    def test_auto_without_a_saved_level_starts_at_the_default_level(self) -> None:
        assert threshold_resolver(_settings("auto", None)).resolve().zipf == 5.0

    def test_the_options_show_auto_at_the_level(self) -> None:
        assert threshold_resolver(_settings("4.0", "A2")).auto_zipf() == 5.5

    def test_fixed_value_ignores_decisions(self) -> None:
        assert threshold_resolver(_settings("5.0"), _friends_pilot()).resolve().zipf == 5.0

    def test_off(self) -> None:
        assert threshold_resolver(_settings("off"), _friends_pilot()).resolve().zipf is None

    def test_missing_or_broken_setting_means_auto(self) -> None:
        assert threshold_resolver(_settings(None), _friends_pilot()).resolve().zipf == 3.5
        assert threshold_resolver(_settings("3.0"), _friends_pilot()).resolve().zipf == 3.5

    def test_resolve_for_a_key_not_saved_yet(self) -> None:
        saved_auto = threshold_resolver(_settings("auto"), _friends_pilot())
        assert saved_auto.resolve_for("5.0").zipf == 5.0
        assert saved_auto.resolve_for("off").zipf is None
        saved_fixed = threshold_resolver(_settings("5.0"), _friends_pilot())
        assert saved_fixed.resolve_for("auto").zipf == 3.5

    def test_resolve_for_a_level_not_saved_yet(self) -> None:
        saved_c1 = threshold_resolver(_settings("auto", "C1"))
        assert saved_c1.resolve_for("auto", CEFRLevel.A2).zipf == 5.5
        assert saved_c1.resolve_for("5.0", CEFRLevel.A2).zipf == 5.0
