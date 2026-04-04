import pytest
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)


@pytest.mark.integration
class TestWordfreqFrequencyProvider:
    def setup_method(self) -> None:
        self.provider = WordfreqFrequencyProvider()

    def test_common_word_high_zipf(self) -> None:
        freq = self.provider.get_frequency("the")
        assert freq.zipf_value > 6.0

    def test_rare_word_low_zipf(self) -> None:
        freq = self.provider.get_frequency("ubiquitous")
        assert freq.zipf_value < 4.0

    def test_sweet_spot_word(self) -> None:
        freq = self.provider.get_frequency("sacrifice")
        assert freq.is_sweet_spot is True

    def test_unknown_word_zero(self) -> None:
        freq = self.provider.get_frequency("asdfghjklzxcv")
        assert freq.zipf_value == 0.0
