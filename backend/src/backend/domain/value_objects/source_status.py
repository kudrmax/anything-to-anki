from __future__ import annotations

from enum import Enum


class SourceStatus(Enum):
    """What became of a source's processing: an outcome. A running operation is not a
    status — the source's operation lock holds it — and how far its review has got is read
    from its progress (`ReviewStatus`)."""

    NEW = "new"
    DONE = "done"
    ERROR = "error"
