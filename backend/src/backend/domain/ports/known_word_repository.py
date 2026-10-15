from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.known_word import KnownWord


class KnownWordRepository(ABC):
    """Port for managing the user's known-word whitelist."""

    @abstractmethod
    def add(self, lemma: str, pos: str | None, *, from_anki: bool = False) -> KnownWord:
        """`from_anki`: the word's note matured in Anki."""

    @abstractmethod
    def remove(self, known_word_id: int) -> None: ...

    @abstractmethod
    def remove_by_lemma(self, lemma: str, pos: str | None) -> None: ...

    @abstractmethod
    def remove_every_pos(self, lemma: str) -> None: ...

    @abstractmethod
    def list_all(self) -> list[KnownWord]: ...

    @abstractmethod
    def exists(self, lemma: str, pos: str | None) -> bool: ...

    @abstractmethod
    def get_all_pairs(self) -> set[tuple[str, str | None]]: ...

    @abstractmethod
    def count(self) -> int: ...
