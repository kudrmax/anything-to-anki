from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.usage_distribution import UsageDistribution


@dataclass(frozen=True)
class WordCandidate:
    """A word identified as worth learning, with context."""

    lemma: str
    pos: str
    cefr_level: CEFRLevel | None
    frequency_band: FrequencyBand
    zipf_frequency: float
    phrase: Phrase
    occurrences: int
    is_phrasal_verb: bool = False
    cefr_breakdown: CEFRBreakdown | None = None
    usage_distribution: UsageDistribution | None = None
    phrase_position: DocumentPosition | None = None
