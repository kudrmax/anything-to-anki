from __future__ import annotations

from pydantic import BaseModel


class StatsDTO(BaseModel):
    """Aggregate statistics for the Inbox. ``ai_unavailable`` — why the AI answers nothing
    while the queue waits for it, as the AI proxy said it."""

    learning_count: int
    export_pending_count: int
    queue_active_count: int
    candidate_count: int
    known_word_count: int
    ai_unavailable: str | None = None
