from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class KnownWord:
    """A word the user already knows (whitelist entry).

    `from_anki`: it became known when its note matured in Anki."""

    lemma: str
    pos: str | None
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    from_anki: bool = False
