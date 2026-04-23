from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Collection:
    """A named group of sources (e.g., a TV series, a book)."""

    name: str
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
