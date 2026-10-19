from abc import ABC, abstractmethod


class FrequencyProvider(ABC):
    """Port for retrieving word frequency data."""

    @abstractmethod
    def get_zipf_value(self, lemma: str) -> float:
        """Get the raw Zipf frequency value for a given lemma."""
