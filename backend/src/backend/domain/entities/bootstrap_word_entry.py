from __future__ import annotations

from dataclasses import dataclass

from backend.domain.value_objects.cefr_level import CEFRLevel


@dataclass(frozen=True)
class BootstrapWordEntry:
    """A word in the bootstrap calibration index with its CEFR level and Zipf frequency."""

    lemma: str
    cefr_level: CEFRLevel
    zipf_value: float
