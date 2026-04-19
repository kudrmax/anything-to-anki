import pytest
from backend.domain.value_objects.frequency_band import FrequencyBand
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)


@pytest.mark.integration
class TestWordfreqFrequencyProvider:
    def setup_method(self) -> None:
        self.provider = WordfreqFrequencyProvider()

    def test_common_word_returns_ultra_common_or_common(self) -> None:
        freq = self.provider.get_frequency("the")
        assert freq in (FrequencyBand.ULTRA_COMMON, FrequencyBand.COMMON)

    def test_rare_word_returns_low_or_rare(self) -> None:
        freq = self.provider.get_frequency("ubiquitous")
        assert freq in (FrequencyBand.LOW, FrequencyBand.RARE, FrequencyBand.MID)

    def test_sweet_spot_word(self) -> None:
        freq = self.provider.get_frequency("sacrifice")
        assert freq.is_sweet_spot is True

    def test_unknown_word_returns_rare(self) -> None:
        freq = self.provider.get_frequency("asdfghjklzxcv")
        assert freq == FrequencyBand.RARE

    def test_get_zipf_value_returns_float(self) -> None:
        zipf = self.provider.get_zipf_value("the")
        assert isinstance(zipf, float)
        assert zipf > 6.0

    def test_get_zipf_value_unknown_word_zero(self) -> None:
        zipf = self.provider.get_zipf_value("asdfghjklzxcv")
        assert zipf == 0.0
