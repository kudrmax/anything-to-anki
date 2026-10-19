from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class KnownWordDTO(BaseModel):
    """An entry of the Known list: a word the user put there (it has an `id`), or one Known
    because its 30 days in Anki passed (`by_timer`, no id; `created_at` is when they did).
    `removal_key` removes it, whichever it is."""

    id: int | None
    lemma: str
    pos: str | None
    created_at: datetime
    removal_key: str
    by_timer: bool = False
