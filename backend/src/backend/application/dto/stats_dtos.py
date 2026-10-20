from __future__ import annotations

from pydantic import BaseModel


class AIOutageDTO(BaseModel):
    """The AI answers no request. ``reason`` — why, as the AI proxy said it;
    ``queue_waits`` — AI work stands in the queue until the AI is back."""

    reason: str
    queue_waits: bool


class StatsDTO(BaseModel):
    """Aggregate statistics for the Inbox, and whether the AI is available."""

    learning_count: int
    export_pending_count: int
    queue_active_count: int
    candidate_count: int
    known_word_count: int
    ai_outage: AIOutageDTO | None = None
