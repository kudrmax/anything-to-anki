from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic needs it at runtime

from pydantic import BaseModel


class AIOutageDTO(BaseModel):
    """The AI answers no request. ``vpn_required`` — a VPN brings it back;
    ``queue_waits`` — AI work stands in the queue until then."""

    reason: str
    since: datetime
    vpn_required: bool
    queue_waits: bool


class StatsDTO(BaseModel):
    """Aggregate statistics for the Inbox, and whether the AI is available."""

    learning_count: int
    export_pending_count: int
    queue_active_count: int
    candidate_count: int
    known_word_count: int
    ai_outage: AIOutageDTO | None = None
