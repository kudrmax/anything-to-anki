from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.entities.anki_note import AnkiNote


class AnkiNoteRepository(ABC):
    """Port for the notes exported to Anki."""

    @abstractmethod
    def add(self, note_id: int, lemma: str, pos: str | None) -> None:
        """Record an exported note; a note already recorded stays as it is."""

    @abstractmethod
    def pending(self) -> list[AnkiNote]:
        """Notes neither mature nor deleted."""

    @abstractmethod
    def mark_matured(self, note_ids: list[int], at: datetime) -> None: ...

    @abstractmethod
    def mark_deleted(self, note_ids: list[int], at: datetime) -> None: ...

    @abstractmethod
    def has_lemma(self, lemma: str) -> bool:
        """A note of this lemma was exported."""
