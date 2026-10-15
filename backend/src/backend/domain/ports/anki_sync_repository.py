from __future__ import annotations

from abc import ABC, abstractmethod


class AnkiSyncRepository(ABC):
    """Port for tracking which phrases have been added to Anki."""

    @abstractmethod
    def get_synced_phrase_ids(self, phrase_ids: list[int]) -> set[int]:
        """The phrases of `phrase_ids` that already have a record in anki_synced_cards."""

    @abstractmethod
    def mark_synced(self, candidate_id: int, anki_note_id: int, phrase_id: int) -> None:
        """Record that the phrase of the word was added to Anki as anki_note_id."""
