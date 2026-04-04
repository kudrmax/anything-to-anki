import pytest
from backend.domain.value_objects.frequency_band import FrequencyBand


@pytest.mark.unit
class TestFrequencyBand:
    def test_from_zipf(self) -> None:
        fb = FrequencyBand.from_zipf(4.0)
        assert fb.zipf_value == 4.0

    def test_from_zipf_negative_clamped(self) -> None:
        fb = FrequencyBand.from_zipf(-1.0)
        assert fb.zipf_value == 0.0

    def test_is_sweet_spot_in_range(self) -> None:
        assert FrequencyBand.from_zipf(3.0).is_sweet_spot is True
        assert FrequencyBand.from_zipf(3.5).is_sweet_spot is True
        assert FrequencyBand.from_zipf(4.5).is_sweet_spot is True

    def test_is_sweet_spot_out_of_range(self) -> None:
        assert FrequencyBand.from_zipf(2.9).is_sweet_spot is False
        assert FrequencyBand.from_zipf(4.6).is_sweet_spot is False
        assert FrequencyBand.from_zipf(7.0).is_sweet_spot is False

    def test_ordering(self) -> None:
        rare = FrequencyBand.from_zipf(2.0)
        common = FrequencyBand.from_zipf(6.0)
        assert rare < common

    def test_frozen(self) -> None:
        fb = FrequencyBand.from_zipf(3.0)
        with pytest.raises(AttributeError):
            fb.zipf_value = 5.0  # type: ignore[misc]
