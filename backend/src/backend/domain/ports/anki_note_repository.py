from __future__ import annotations

from abc import ABC, abstractmethod


class AnkiNoteRepository(ABC):
    """Port for the notes exported to Anki."""

    @abstractmethod
    def add(self, note_id: int, lemma: str, pos: str | None) -> None:
        """Record an exported note; a note already recorded stays as it is."""
