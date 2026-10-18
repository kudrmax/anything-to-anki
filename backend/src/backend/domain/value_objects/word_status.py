from __future__ import annotations

from enum import StrEnum


class WordStatus(StrEnum):
    """The user's decision on a word of a source."""

    NEW = "pending"
    LEARN = "learn"
    KNOWN = "known"
