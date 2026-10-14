from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class UnknownWordDTO(BaseModel):
    """A word the user said they don't know."""

    id: int
    lemma: str
    created_at: datetime
