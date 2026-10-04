from __future__ import annotations

from enum import StrEnum


class GenerationScope(StrEnum):
    """Which cards of a source a generation request covers."""

    MISSING = "missing"
    """Cards nothing was made for yet and nothing is being made for."""
    FAILED = "failed"
    """Cards whose last attempt failed."""
    ALL = "all"
    """Every card: what is there gets replaced."""
