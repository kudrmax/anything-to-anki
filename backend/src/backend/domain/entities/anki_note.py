from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AnkiNote:
    """A note exported to Anki, kept whatever happens to the source it came from.

    `matured_at`: when it was found mature (its word became Known); `deleted_at`: when it
    was found deleted in Anki.
    """

    note_id: int
    lemma: str
    pos: str | None
    matured_at: datetime | None = None
    deleted_at: datetime | None = None
