from __future__ import annotations

from enum import Enum


class CandidateStatus(Enum):
    """User-assigned status of a word candidate."""

    PENDING = "pending"
    LEARN = "learn"
    KNOWN = "known"
    SKIP = "skip"
