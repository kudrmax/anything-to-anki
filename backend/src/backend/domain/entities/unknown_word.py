from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class UnknownWord:
    """A word the user said they don't know."""

    lemma: str
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
