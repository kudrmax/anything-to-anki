from abc import ABC, abstractmethod

from backend.domain.entities.token_data import TokenData
from backend.domain.services.long_operation_progress import PartReport, no_report


class TextAnalyzer(ABC):
    """Port for NLP analysis: tokenization, lemmatization, POS tagging, dependency parsing."""

    @abstractmethod
    def analyze(self, text: str, report: PartReport = no_report) -> list[TokenData]:
        """Analyze text and return a list of token data objects; `report` is told the share
        of the text analysed, ending at 1."""
