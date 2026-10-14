from __future__ import annotations

from wordfreq import zipf_frequency

from backend.domain.ports.frequency_provider import FrequencyProvider


class WordfreqFrequencyProvider(FrequencyProvider):
    """Provides word frequency data using the wordfreq library."""

    def get_zipf_value(self, lemma: str) -> float:
        return zipf_frequency(lemma.lower(), "en")
