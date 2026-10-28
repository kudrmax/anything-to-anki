import itertools

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FrequentWordThreshold,
    auto_start_zipf,
    step_index,
)


@pytest.mark.unit
class TestFrequentWordThreshold:
    def test_word_at_threshold_is_covered(self) -> None:
        assert FrequentWordThreshold.from_key("4.5").covers(4.5) is True

    def test_rarer_word_is_not_covered(self) -> None:
        assert FrequentWordThreshold.from_key("4.5").covers(4.49) is False

    def test_off_covers_nothing(self) -> None:
        assert FrequentWordThreshold.from_key("off").covers(7.0) is False

    def test_default_is_auto(self) -> None:
        assert DEFAULT_FREQUENT_WORD_THRESHOLD.is_auto

    def test_auto_covers_nothing_until_calibrated(self) -> None:
        auto = FrequentWordThreshold.from_key("auto")
        assert auto.covers(7.0) is False
        assert auto.calibrated(3.5).covers(3.5) is True

    def test_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            FrequentWordThreshold.from_key("3.0")


@pytest.mark.unit
class TestAutoStart:
    @pytest.mark.parametrize(
        ("level", "zipf"),
        [
            (CEFRLevel.A1, 5.5), (CEFRLevel.A2, 5.5), (CEFRLevel.B1, 5.0),
            (CEFRLevel.B2, 4.5), (CEFRLevel.C1, 4.0), (CEFRLevel.C2, 4.0),
        ],
    )
    def test_starts_where_a_learner_of_the_level_probably_knows_a_word(
        self, level: CEFRLevel, zipf: float,
    ) -> None:
        assert auto_start_zipf(level) == zipf

    def test_a_higher_level_never_starts_higher(self) -> None:
        starts = [auto_start_zipf(level) for level in CEFRLevel]
        assert all(a >= b for a, b in itertools.pairwise(starts))

    def test_every_start_is_a_step(self) -> None:
        for level in CEFRLevel:
            step_index(auto_start_zipf(level))
