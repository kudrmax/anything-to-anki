from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.frequency_band import FrequencyBand


@dataclass(frozen=True)
class WordCandidate:
    """A word identified as worth learning, with context."""

    lemma: str
    pos: str
    cefr_level: CEFRLevel
    frequency_band: FrequencyBand
    context_fragment: str
    fragment_unknown_count: int
    occurrences: int
    is_phrasal_verb: bool = False
    surface_form: str | None = None  # Actual form in text, e.g. "gave up" for lemma "give up"
