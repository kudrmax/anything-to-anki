import pytest
from backend.domain.value_objects.frequency_band import FrequencyBand


@pytest.mark.unit
class TestFrequencyBand:
    def test_from_zipf_ultra_common(self) -> None:
        assert FrequencyBand.from_zipf(5.5) == FrequencyBand.ULTRA_COMMON
        assert FrequencyBand.from_zipf(7.0) == FrequencyBand.ULTRA_COMMON

    def test_from_zipf_common(self) -> None:
        assert FrequencyBand.from_zipf(4.5) == FrequencyBand.COMMON
        assert FrequencyBand.from_zipf(5.0) == FrequencyBand.COMMON
        assert FrequencyBand.from_zipf(5.49) == FrequencyBand.COMMON

    def test_from_zipf_mid(self) -> None:
        assert FrequencyBand.from_zipf(3.5) == FrequencyBand.MID
        assert FrequencyBand.from_zipf(4.0) == FrequencyBand.MID
        assert FrequencyBand.from_zipf(4.49) == FrequencyBand.MID

    def test_from_zipf_low(self) -> None:
        assert FrequencyBand.from_zipf(2.5) == FrequencyBand.LOW
        assert FrequencyBand.from_zipf(3.0) == FrequencyBand.LOW
        assert FrequencyBand.from_zipf(3.49) == FrequencyBand.LOW

    def test_from_zipf_rare(self) -> None:
        assert FrequencyBand.from_zipf(0.0) == FrequencyBand.RARE
        assert FrequencyBand.from_zipf(2.0) == FrequencyBand.RARE
        assert FrequencyBand.from_zipf(2.49) == FrequencyBand.RARE

    def test_from_zipf_negative_clamped(self) -> None:
        assert FrequencyBand.from_zipf(-1.0) == FrequencyBand.RARE

    def test_is_sweet_spot(self) -> None:
        assert FrequencyBand.MID.is_sweet_spot is True
        assert FrequencyBand.COMMON.is_sweet_spot is False
        assert FrequencyBand.LOW.is_sweet_spot is False
        assert FrequencyBand.RARE.is_sweet_spot is False
        assert FrequencyBand.ULTRA_COMMON.is_sweet_spot is False

    def test_sort_value_ordering(self) -> None:
        """Higher sort_value = more frequent band."""
        assert FrequencyBand.ULTRA_COMMON.value > FrequencyBand.COMMON.value
        assert FrequencyBand.COMMON.value > FrequencyBand.MID.value
        assert FrequencyBand.MID.value > FrequencyBand.LOW.value
        assert FrequencyBand.LOW.value > FrequencyBand.RARE.value
