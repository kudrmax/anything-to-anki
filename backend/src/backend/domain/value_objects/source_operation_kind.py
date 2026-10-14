from __future__ import annotations

from enum import StrEnum


class SourceOperationKind(StrEnum):
    """A long operation that holds a source: no other one may run on it meanwhile."""

    PROCESS = "process"
    REBUILD = "rebuild"
    PREVIEW = "preview"
    REFRESH = "refresh"
