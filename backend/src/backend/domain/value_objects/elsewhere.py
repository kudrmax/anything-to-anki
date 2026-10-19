from __future__ import annotations

from enum import StrEnum


class ElsewhereStatus(StrEnum):
    """Why a word still open in this source counts as done: the user knows it, is learning it
    in Anki, or marked it Learn and has not exported it yet, via another source."""

    KNOWN = "known"
    LEARNING = "learning"
    LEARN = "learn"
