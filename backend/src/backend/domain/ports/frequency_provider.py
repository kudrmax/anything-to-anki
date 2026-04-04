from abc import ABC, abstractmethod

from backend.domain.value_objects.frequency_band import FrequencyBand


class FrequencyProvider(ABC):
    """Port for retrieving word frequency data."""

    @abstractmethod
    def get_frequency(self, lemma: str) -> FrequencyBand:
        """Get the frequency band for a given lemma."""
