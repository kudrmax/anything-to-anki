from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResult:
    """Result of AI meaning generation."""

    meaning: str
    tokens_used: int
