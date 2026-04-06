from __future__ import annotations
from enum import Enum


class MediaExtractionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
