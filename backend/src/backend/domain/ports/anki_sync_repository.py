from __future__ import annotations

from abc import ABC, abstractmethod


class AnkiSyncRepository(ABC):
    """Port for tracking which candidates have been synced to Anki."""

    @abstractmethod
    def get_synced_candidate_ids(self, candidate_ids: list[int]) -> set[int]:
        """Return the subset of candidate_ids that already have a record in anki_synced_cards."""

    @abstractmethod
    def mark_synced(self, candidate_id: int, anki_note_id: int) -> None:
        """Record that candidate_id was successfully added to Anki as anki_note_id."""
