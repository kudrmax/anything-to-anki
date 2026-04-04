from __future__ import annotations

from abc import ABC, abstractmethod


class AnkiConnector(ABC):
    """Port for communicating with AnkiConnect."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if AnkiConnect is reachable."""

    @abstractmethod
    def ensure_note_type(self, model_name: str, fields: list[str]) -> None:
        """Create the note type if it does not exist yet."""

    @abstractmethod
    def ensure_deck(self, deck_name: str) -> None:
        """Create the deck if it does not exist yet."""

    @abstractmethod
    def find_notes_by_target(self, deck_name: str, target: str) -> list[int]:
        """Return note IDs that match the given target lemma in the deck."""

    @abstractmethod
    def add_notes(
        self,
        deck_name: str,
        model_name: str,
        notes: list[dict[str, str]],
    ) -> list[int | None]:
        """Add notes to Anki. Returns list of new note IDs (None on failure)."""
