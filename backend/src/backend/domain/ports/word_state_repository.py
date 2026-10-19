from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection
    from contextlib import AbstractContextManager

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
    def of_words(self, word_ids: Collection[int]) -> dict[int, WordState]:
        """The words with these ids, by id; an unknown id is left out."""

    @abstractmethod
    def of_lemma(self, lemma: str) -> list[WordState]:
        """Every word of the lemma in every source, compared in lowercase."""

    @abstractmethod
    def save(self, word: WordState) -> None:
        """Writes the choice of every card, onto its active binding too, and the word's
        decision status; binding and release are the Anki sync repository's."""

    @abstractmethod
    def batch(self) -> AbstractContextManager[None]:
        """Many saves in one go: what a save makes stale is refreshed once, at the end."""
