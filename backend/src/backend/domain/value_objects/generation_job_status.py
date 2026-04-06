from __future__ import annotations

from enum import Enum


class GenerationJobStatus(Enum):
    """Status of a background definition generation job."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
