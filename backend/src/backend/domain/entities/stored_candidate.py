from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.value_objects.candidate_status import CandidateStatus
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.usage_distribution import UsageDistribution


@dataclass
class StoredCandidate:
    """A word candidate persisted after source processing.

    `meaning` and `media` are nested enrichment objects (1:1) that may be None
    if no generation/extraction has been attempted yet. They live in their own
    tables (`candidate_meanings`, `candidate_media`) but are loaded together
    with the candidate by the repository.
    """

    source_id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    context_fragment: str
    fragment_purity: str
    occurrences: int
    status: CandidateStatus
    surface_form: str | None = None
    is_phrasal_verb: bool = False
    has_custom_context_fragment: bool = False
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    pronunciation: CandidatePronunciation | None = None
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
