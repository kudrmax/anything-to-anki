from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchMeaningResult:
    """A single result from batch meaning generation."""

    word_index: int
    meaning: str
    ipa: str | None
