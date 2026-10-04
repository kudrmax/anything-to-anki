from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.value_objects.candidate_status import CandidateStatus
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.phrase_origin import PhraseOrigin
    from backend.domain.value_objects.usage_distribution import UsageDistribution

NOUN_POS = "NOUN"


@dataclass
class StoredCandidate:
    """A word candidate persisted after source processing.

    `meaning` and `media` are nested enrichment objects (1:1) that may be None
    if no generation/extraction has been attempted yet. They live in their own
    tables (`candidate_meanings`, `candidate_media`) but are loaded together
    with the candidate by the repository.

    `origin` is set only when the phrase was borrowed from another source or
    generated — candidates of a topic source.

    `fragment_unknown_count` is how many words of the phrase besides the
    target the user probably does not know.

    `context_fragment` is the phrase as it stands in the source. AI may polish
    it into an easier `polished_fragment`; the card shows the polished one
    unless the user reverted it.
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
    tts: CandidateTTS | None = None
    id: int | None = None
    cefr_breakdown: CEFRBreakdown | None = None
    usage_distribution: UsageDistribution | None = None
    origin: PhraseOrigin | None = None
    fragment_unknown_count: int = 0
    polished_fragment: str | None = None
    polish_reverted: bool = False

    @property
    def is_polished(self) -> bool:
        """AI rewrote the phrase. A phrase AI left as is does not count."""
        polished = self.polished_fragment
        return polished is not None and polished != self.context_fragment

    @property
    def card_phrase(self) -> str:
        """The phrase the card shows, speaks and exports."""
        if self.polished_fragment is not None and not self.polish_reverted:
            return self.polished_fragment
        return self.context_fragment

    @property
    def can_have_target_image(self) -> bool:
        """Only nouns get a picture: other targets rarely have one that explains them."""
        return self.pos == NOUN_POS and not self.is_phrasal_verb

    @property
    def frequency_band(self) -> FrequencyBand:
        from backend.domain.value_objects.frequency_band import FrequencyBand
        return FrequencyBand.from_zipf(self.zipf_frequency)

    @property
    def is_sweet_spot(self) -> bool:
        return self.frequency_band.is_sweet_spot
