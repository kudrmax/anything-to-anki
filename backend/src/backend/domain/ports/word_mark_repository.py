from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.known_word import KnownWord
    from backend.domain.entities.unknown_word import UnknownWord


class WordMarkRepository(ABC):
    """Port for the user's marks on lemmas: Known (in some parts of speech) or Unknown, never
    both. Lemmas are matched lower-case. A Known entry with no pos means any part of speech
    and absorbs the others."""

    @abstractmethod
    def mark_known(self, lemma: str, pos: str | None) -> KnownWord:
        """Known in `pos`; an Unknown mark of the lemma gives way. Returns the entry that
        covers `pos`."""

    @abstractmethod
    def mark_unknown(self, lemma: str) -> UnknownWord:
        """Unknown; a Known mark of the lemma gives way with all its parts of speech."""

    @abstractmethod
    def remove_known_entry(self, lemma: str, pos: str | None) -> None:
        """One Known entry; removing the lemma's last one removes its mark."""

    @abstractmethod
    def remove_known(self, lemma: str) -> None:
        """The Known mark with every part of speech."""

    @abstractmethod
    def remove_unknown(self, lemma: str) -> None: ...

    @abstractmethod
    def known_entries(self) -> list[KnownWord]:
        """Every Known (lemma, pos) entry, newest mark first."""

    @abstractmethod
    def unknown_entries(self) -> list[UnknownWord]:
        """Every Unknown lemma, newest first."""

    @abstractmethod
    def known_lemmas(self) -> set[str]: ...

    @abstractmethod
    def unknown_lemmas(self) -> set[str]: ...

    @abstractmethod
    def known_count(self) -> int:
        """Lemmas marked Known."""

    @abstractmethod
    def unknown_count(self) -> int:
        """Lemmas marked Unknown."""
