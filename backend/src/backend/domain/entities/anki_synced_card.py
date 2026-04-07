from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnkiSyncedCard:
    """Records that a candidate was successfully added to Anki."""

    candidate_id: int
    anki_note_id: int
    id: int | None = None
