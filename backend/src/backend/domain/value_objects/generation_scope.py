from __future__ import annotations

from enum import StrEnum


class GenerationScope(StrEnum):
    """Which cards of a source a generation request covers."""

    NEXT = "next"
    """The first missing cards in the order the list shows them, a batch of them at most."""
    MISSING = "missing"
    """Cards nothing was made for yet and nothing is being made for."""
    READY_NEXT = "ready_next"
    """The first missing cards of the Ready section, a batch of them at most."""
    READY_MISSING = "ready_missing"
    """Missing cards that are in the Ready section right now."""
    READY_ALL = "ready_all"
    """Every card in the Ready section right now: what is there gets replaced."""
    FAILED = "failed"
    """Cards whose last attempt failed."""
    ALL = "all"
    """Every card: what is there gets replaced."""
