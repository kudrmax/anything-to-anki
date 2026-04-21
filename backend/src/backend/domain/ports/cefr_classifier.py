from abc import ABC, abstractmethod

from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel


class CEFRClassifier(ABC):
    """Port for classifying words by CEFR level."""

    @abstractmethod
    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        """Classify a word (lemma + Penn Treebank POS tag) into a CEFR level."""

    def classify_detailed(self, lemma: str, pos_tag: str) -> CEFRBreakdown:
        """Classify with full breakdown. Override for detailed results."""
        level = self.classify(lemma, pos_tag)
        return CEFRBreakdown(
            final_level=level,
            decision_method="voting",
            priority_votes=[],
            votes=[],
        )
