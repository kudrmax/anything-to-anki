from __future__ import annotations

from abc import ABC, abstractmethod


class AnkiConnector(ABC):
    """Port for communicating with AnkiConnect."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if AnkiConnect is reachable."""

    @abstractmethod
    def ensure_note_type(self, model_name: str, fields: list[str]) -> None:
        """Ensure the note type exists and contains all of the listed fields.

        If the note type does not exist, create it with exactly the listed
        fields. If it exists, add any missing fields to it (existing extra
        fields are preserved). When creating a new model, the order of
        fields matches the order of the input list.
        """

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

    @abstractmethod
    def get_model_field_names(self, model_name: str) -> list[str] | None:
        """Return field names for the given note type, or None if it doesn't exist."""

    @abstractmethod
    def store_media_file(self, filename: str, file_path: str) -> None:
        """Copy a local file to Anki's media folder via AnkiConnect."""
