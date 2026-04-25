from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class KnownWordDTO(BaseModel):
    """A known-word whitelist entry."""

    id: int
    lemma: str
    pos: str | None
    created_at: datetime
