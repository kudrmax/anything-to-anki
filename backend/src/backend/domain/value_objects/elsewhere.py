from __future__ import annotations

from enum import StrEnum


class ElsewhereStatus(StrEnum):
    """Why a word still open in this source counts as done: the user knows it, or learns it
    via another source."""

    KNOWN = "known"
    LEARNING = "learning"
