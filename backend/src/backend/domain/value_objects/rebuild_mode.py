from __future__ import annotations

from enum import StrEnum


class RebuildMode(StrEnum):
    """How far a rebuild of a source goes.

    UPDATE: lays the cards out by what the user knows now; no phrase text changes.
    RECUT: also cuts the phrases again, dropping what was made of their old text.
    """

    UPDATE = "update"
    RECUT = "recut"
