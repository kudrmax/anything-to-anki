from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.known_word import KnownWord


class KnownWordRepository(ABC):
    """Port for managing the user's known-word whitelist."""

    @abstractmethod
    def add(self, lemma: str, pos: str) -> KnownWord: ...

    @abstractmethod
    def remove(self, known_word_id: int) -> None: ...

    @abstractmethod
    def list_all(self) -> list[KnownWord]: ...

    @abstractmethod
    def exists(self, lemma: str, pos: str) -> bool: ...

    @abstractmethod
    def get_all_pairs(self) -> set[tuple[str, str]]: ...

    @abstractmethod
    def count(self) -> int: ...
