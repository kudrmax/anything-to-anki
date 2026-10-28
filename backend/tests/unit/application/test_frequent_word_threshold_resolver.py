from unittest.mock import MagicMock

import pytest

from tests.candidate_sorter_support import threshold_resolver


def _settings(value: str | None) -> MagicMock:
    saved = {"frequent_word_threshold": value}
    repo = MagicMock()
    repo.get.side_effect = lambda key, default=None: saved.get(key) or default
    return repo


@pytest.mark.unit
class TestFrequentWordThresholdResolver:
    def test_a_saved_value_is_resolved(self) -> None:
        assert threshold_resolver(_settings("5.0")).resolve().zipf == 5.0

    def test_off_has_no_threshold(self) -> None:
        assert threshold_resolver(_settings("off")).resolve().zipf is None

    @pytest.mark.parametrize("saved", [None, "3.0", "auto"])
    def test_a_missing_broken_or_removed_setting_means_off(self, saved: str | None) -> None:
        assert threshold_resolver(_settings(saved)).resolve().key == "off"

    def test_resolve_for_a_key_not_saved_yet(self) -> None:
        saved_off = threshold_resolver(_settings("off"))
        assert saved_off.resolve_for("5.0").zipf == 5.0
        assert saved_off.resolve_for("auto").key == "off"
