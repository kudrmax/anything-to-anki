from __future__ import annotations

from enum import Enum


class SourceStatus(Enum):
    """What became of a source: an outcome. A running operation is not a status — the
    source's operation lock holds it."""

    NEW = "new"
    DONE = "done"
    ERROR = "error"
    PARTIALLY_REVIEWED = "partially_reviewed"
    REVIEWED = "reviewed"
