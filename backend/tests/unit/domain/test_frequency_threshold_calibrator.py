import pytest
from backend.domain.entities.word_decision import WordDecision
from backend.domain.services.frequency_threshold_calibrator import (
    FrequencyThresholdCalibrator,
)


def _decisions(zipf: float, known: int, learn: int) -> list[WordDecision]:
    return [WordDecision(f"k{zipf}{i}", zipf, True) for i in range(known)] + [
        WordDecision(f"l{zipf}{i}", zipf, False) for i in range(learn)
    ]


@pytest.mark.unit
class TestFrequencyThresholdCalibrator:
    def test_no_decisions_keeps_the_start(self) -> None:
        assert FrequencyThresholdCalibrator().calibrate([]) == 4.5

    def test_goes_down_while_bands_are_mostly_known(self) -> None:
        """Friends pilot: 9 of 11 known in 4.0-4.5, 6 of 8 in 3.5-4.0."""
        decisions = _decisions(4.2, known=9, learn=2) + _decisions(3.7, known=6, learn=2)
        assert FrequencyThresholdCalibrator().calibrate(decisions) == 3.5

    def test_stops_at_a_mostly_unknown_band(self) -> None:
        decisions = (
            _decisions(4.2, known=5, learn=0)
            + _decisions(3.7, known=1, learn=4)
            + _decisions(3.2, known=5, learn=0)
        )
        assert FrequencyThresholdCalibrator().calibrate(decisions) == 4.0

    def test_stops_at_a_band_with_too_few_decisions(self) -> None:
        decisions = _decisions(4.2, known=3, learn=0) + _decisions(3.7, known=9, learn=0)
        assert FrequencyThresholdCalibrator().calibrate(decisions) == 4.5

    def test_goes_up_while_bands_above_are_mostly_unknown(self) -> None:
        decisions = _decisions(4.7, known=1, learn=4) + _decisions(5.2, known=4, learn=1)
        assert FrequencyThresholdCalibrator().calibrate(decisions) == 5.0

    def test_never_goes_below_the_lowest_band(self) -> None:
        decisions = [
            d for z in (4.2, 3.7, 3.2, 2.7, 2.2, 1.7) for d in _decisions(z, known=5, learn=0)
        ]
        assert FrequencyThresholdCalibrator().calibrate(decisions) == 2.5
