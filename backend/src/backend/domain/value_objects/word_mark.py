from __future__ import annotations

from enum import StrEnum


class WordMark(StrEnum):
    """The one mark a lemma can carry: the user knows it, or said they don't."""

    KNOWN = "known"
    UNKNOWN = "unknown"
