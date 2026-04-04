from __future__ import annotations

from enum import Enum


class SourceStatus(Enum):
    """Status of a text source in the processing pipeline."""

    NEW = "new"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    PARTIALLY_REVIEWED = "partially_reviewed"
    REVIEWED = "reviewed"
