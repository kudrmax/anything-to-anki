from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.unknown_word import UnknownWord


class UnknownWordRepository(ABC):
    """Port for the words the user said they don't know."""

    @abstractmethod
    def add(self, lemma: str) -> UnknownWord: ...

    @abstractmethod
    def remove(self, unknown_word_id: int) -> None: ...

    @abstractmethod
    def remove_by_lemma(self, lemma: str) -> None: ...

    @abstractmethod
    def list_all(self) -> list[UnknownWord]: ...

    @abstractmethod
    def lemmas(self) -> set[str]: ...

    @abstractmethod
    def count(self) -> int: ...
