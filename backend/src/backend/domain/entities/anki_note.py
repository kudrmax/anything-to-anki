from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnkiNote:
    """A note exported to Anki, kept whatever happens to the source it came from."""

    note_id: int
    lemma: str
    pos: str | None
