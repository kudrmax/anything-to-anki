from __future__ import annotations

from enum import Enum


class MediaExtractionJobStatus(Enum):
    """Status of a background media extraction job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
