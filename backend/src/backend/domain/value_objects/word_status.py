from __future__ import annotations

from enum import StrEnum


class WordStatus(StrEnum):
    """What every reader sees of a word: its decision, and Learning read as Known after the
    timer."""

    NEW = "pending"
    LEARN = "learn"
    LEARNING = "learning"
    KNOWN = "known"
