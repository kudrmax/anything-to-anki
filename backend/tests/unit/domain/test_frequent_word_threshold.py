import pytest
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
)


@pytest.mark.unit
class TestFrequentWordThreshold:
    def test_word_at_threshold_is_covered(self) -> None:
        assert FrequentWordThreshold.from_key("4.5").covers(4.5) is True

    def test_rarer_word_is_not_covered(self) -> None:
        assert FrequentWordThreshold.from_key("4.5").covers(4.49) is False

    def test_off_covers_nothing(self) -> None:
        assert FrequentWordThreshold.from_key("off").covers(7.0) is False

    def test_default_is_four_and_a_half(self) -> None:
        assert DEFAULT_FREQUENT_WORD_THRESHOLD.zipf == 4.5

    def test_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            FrequentWordThreshold.from_key("3.0")
