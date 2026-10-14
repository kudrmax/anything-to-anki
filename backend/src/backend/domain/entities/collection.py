from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Collection:
    """A named group of sources (a series, a book, an exam topic); a top-level one may hold
    subcollections."""

    name: str
    id: int | None = None
    parent_id: int | None = None
    position: int = 0
    deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def is_top_level(self) -> bool:
        return self.parent_id is None
