from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.card_choice import WordState


class WordStateRepository(ABC):
    """Port for words as the decision tables see them: every card's choice and active
    binding."""

    @abstractmethod
    def of_word(self, word_id: int) -> WordState | None: ...

    @abstractmethod
    def of_source(self, source_id: int) -> dict[int, WordState]:
        """Every word of the source, by id."""

    @abstractmethod
    def of_lemma(self, lemma: str) -> list[WordState]:
        """Every word of the lemma in every source, compared in lowercase."""

    @abstractmethod
    def save(self, word: WordState) -> None:
        """Writes the choice of every card and the word's decision status; bindings are the
        Anki sync repository's."""
