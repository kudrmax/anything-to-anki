from abc import ABC, abstractmethod

from backend.domain.value_objects.cefr_level import CEFRLevel


class CEFRClassifier(ABC):
    """Port for classifying words by CEFR level."""

    @abstractmethod
    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        """Classify a word (lemma + Penn Treebank POS tag) into a CEFR level."""
