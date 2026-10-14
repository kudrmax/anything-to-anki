from __future__ import annotations

from dataclasses import dataclass

# Anki's own threshold: a card is mature once its interval reaches 21 days.
MATURE_INTERVAL_DAYS = 21


@dataclass(frozen=True)
class NoteCards:
    """The cards of one Anki note: intervals of the active ones, in days, and how many are
    suspended. A card in (re)learning has a negative interval (seconds)."""

    intervals: tuple[int, ...]
    suspended: int


def is_mature(cards: NoteCards) -> bool:
    """Learned: has an active card and every active card reached the mature interval."""
    return bool(cards.intervals) and all(i >= MATURE_INTERVAL_DAYS for i in cards.intervals)
