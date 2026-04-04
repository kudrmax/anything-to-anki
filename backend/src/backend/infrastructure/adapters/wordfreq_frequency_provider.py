from __future__ import annotations

from wordfreq import zipf_frequency

from backend.domain.ports.frequency_provider import FrequencyProvider
from backend.domain.value_objects.frequency_band import FrequencyBand


class WordfreqFrequencyProvider(FrequencyProvider):
    """Provides word frequency data using the wordfreq library."""

    def get_frequency(self, lemma: str) -> FrequencyBand:
        zipf = zipf_frequency(lemma.lower(), "en")
        return FrequencyBand.from_zipf(zipf)
