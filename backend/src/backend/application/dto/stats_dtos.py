from __future__ import annotations

from pydantic import BaseModel


class StatsDTO(BaseModel):
    """Aggregate statistics for the Inbox."""

    learn_count: int
    export_pending_count: int
    candidate_count: int
    known_word_count: int
