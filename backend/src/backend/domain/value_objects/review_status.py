from __future__ import annotations

from enum import Enum


class ReviewStatus(Enum):
    """The status a source reads as: its stored outcome, and for a processed source how far
    its review has got by the progress at that moment. It is derived on read, never stored."""

    NEW = "new"
    ERROR = "error"
    DONE = "done"
    PARTIALLY_REVIEWED = "partially_reviewed"
    REVIEWED = "reviewed"
