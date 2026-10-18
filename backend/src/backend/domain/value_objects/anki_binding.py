from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.card_choice import NoteKind


@dataclass(frozen=True)
class AnkiBinding:
    """A new active binding of a card to its Anki note; its timer starts at `learning_since`."""

    word_id: int
    phrase_id: int
    note_id: int
    lemma: str
    pos: str | None
    note_kind: NoteKind
    learning_since: datetime
