from __future__ import annotations

from enum import Enum


class LongOperationKind(Enum):
    """A long operation over sources: while it runs, nothing else writes."""

    LEVEL_CHANGE = "level_change"
    PROCESS = "process"
    UPDATE = "update"
    RECUT = "recut"
    REFRESH = "refresh"
