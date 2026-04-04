from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class KnownWord:
    """A word the user already knows (whitelist entry)."""

    lemma: str
    pos: str
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
