from __future__ import annotations

from enum import StrEnum


class CardGenerationState(StrEnum):
    """Where one card stands with one kind of generation."""

    DONE = "done"
    RUNNING = "running"
    FAILED = "failed"
    MISSING = "missing"
