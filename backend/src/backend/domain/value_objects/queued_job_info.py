from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueuedJobInfo:
    """A single job in the arq queue or currently running."""

    job_id: str
    job_type: str  # "meanings" | "media" | "pronunciation" | "youtube_dl"
    source_id: int
    position: int | None  # ordinal for queued, None for running
    scheduled_at: float  # Unix timestamp from Redis ZSET score
