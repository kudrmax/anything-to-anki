from abc import ABC, abstractmethod

from backend.domain.entities.token_data import TokenData


class TextAnalyzer(ABC):
    """Port for NLP analysis: tokenization, lemmatization, POS tagging, dependency parsing."""

    @abstractmethod
    def analyze(self, text: str) -> list[TokenData]:
        """Analyze text and return a list of token data objects."""
