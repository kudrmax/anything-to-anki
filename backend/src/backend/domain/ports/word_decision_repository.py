from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.word_decision import WordDecision


class WordDecisionRepository(ABC):
    """Port for the user's verdicts on words, one per lemma."""

    @abstractmethod
    def record(self, decision: WordDecision) -> None:
        """Save the decision, replacing an earlier one on the same lemma."""

    @abstractmethod
    def forget(self, lemma: str) -> None: ...

    @abstractmethod
    def list_all(self) -> list[WordDecision]: ...
