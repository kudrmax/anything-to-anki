from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResult:
    """Result of AI meaning generation."""

    meaning: str
    translation: str
    synonyms: str
    ipa: str | None
    tokens_used: int
