from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.usage_distribution import UsageDistribution
    from backend.domain.value_objects.word_status import WordStatus


@dataclass
class StoredCandidate:
    """A word of a source: one per lemma (and phrasal-verb flag), with the decision on it.
    Its phrases are `Occurrence`s.

    `pronunciation` and `meaning_image` belong to the word and are loaded with it; they may
    be None when nothing was made yet.

    `was_unknown`: the user had marked the lemma unknown before its Known — undoing it marks
    it unknown again.
    """

    source_id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    occurrences: int
    status: WordStatus
    is_phrasal_verb: bool = False
    was_unknown: bool = False
    pronunciation: CandidatePronunciation | None = None
    meaning_image: CandidateMeaningImage | None = None
    id: int | None = None
    cefr_breakdown: CEFRBreakdown | None = None
    usage_distribution: UsageDistribution | None = None

    @property
    def frequency_band(self) -> FrequencyBand:
        from backend.domain.value_objects.frequency_band import FrequencyBand
        return FrequencyBand.from_zipf(self.zipf_frequency)

    @property
    def is_sweet_spot(self) -> bool:
        return self.frequency_band.is_sweet_spot
