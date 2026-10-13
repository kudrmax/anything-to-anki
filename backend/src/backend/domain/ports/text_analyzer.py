from abc import ABC, abstractmethod

from backend.domain.entities.token_data import TokenData


class TextAnalyzer(ABC):
    """Port for NLP analysis: tokenization, lemmatization, POS tagging, dependency parsing."""

    @abstractmethod
    def analyze(self, text: str, sentence_starts: frozenset[int] = frozenset()) -> list[TokenData]:
        """Analyze text and return a list of token data objects.

        A token at one of `sentence_starts` (character offsets) begins a sentence.
        """
