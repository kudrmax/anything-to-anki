from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.candidate_status import CandidateStatus
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin
    from backend.domain.value_objects.usage_distribution import UsageDistribution

@dataclass
class StoredCandidate:
    """A word of a source: one per lemma (and phrasal-verb flag).
    Its occurrences are `Occurrence`s.

    A word candidate persisted after source processing.

    `meaning` and `media` are nested enrichment objects (1:1) that may be None
    if no generation/extraction has been attempted yet. They live in their own
    tables (`candidate_meanings`, `candidate_media`) but are loaded together
    with the candidate by the repository.

    `origin` is set only when the phrase was borrowed from another source or
    generated — candidates of a topic source.

    `source_phrase` is the phrase as it stands in the source. AI may polish it
    into an easier `polished_phrase`, or the user may rewrite it there by hand;
    the card shows the polished one unless the user reverted it. A polished
    phrase with the source's text means AI left it as is.

    `cloze` is the markup of the cloze card, if the user made one.

    `meaning_image` is a picture of the target the user picked; the video
    frame of the phrase is in `media`.

    `phrase_position` places the source phrase in the source's document. A phrase
    that isn't there (an example, a topic's or a saved phrase) has none.
    """

    source_id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    # TRANSITIONAL(words-phrases): removed in Task 10
    source_phrase: Phrase
    occurrences: int
    status: CandidateStatus
    is_phrasal_verb: bool = False
    # TRANSITIONAL(words-phrases): removed in Task 10
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    pronunciation: CandidatePronunciation | None = None
    # TRANSITIONAL(words-phrases): removed in Task 10
    tts: CandidateTTS | None = None
    # TRANSITIONAL(words-phrases): removed in Task 10
    cloze: CandidateCloze | None = None
    meaning_image: CandidateMeaningImage | None = None
    id: int | None = None
    cefr_breakdown: CEFRBreakdown | None = None
    usage_distribution: UsageDistribution | None = None
    origin: PhraseOrigin | None = None
    # TRANSITIONAL(words-phrases): removed in Task 10
    polished_phrase: Phrase | None = None
    polish_reverted: bool = False
    phrase_position: DocumentPosition | None = None
    # TRANSITIONAL(words-phrases): removed in Task 10 — written to the new phrase, not read back
    occurrence_key: OccurrenceKey | None = None
    fragment_score: float | None = None
    # TRANSITIONAL(words-phrases): removed in Task 10 — the phrase the card is seen through
    phrase_id: int | None = None

    # TRANSITIONAL(words-phrases): removed in Task 10
    @property
    def is_polished(self) -> bool:
        """The phrase was rewritten. A phrase AI left as is does not count."""
        polished = self.polished_phrase
        return polished is not None and polished.text != self.source_phrase.text

    # TRANSITIONAL(words-phrases): removed in Task 10
    @property
    def phrase(self) -> Phrase:
        """The phrase the card shows, speaks and exports."""
        if self.polished_phrase is not None and not self.polish_reverted:
            return self.polished_phrase
        return self.source_phrase

    @property
    def frequency_band(self) -> FrequencyBand:
        from backend.domain.value_objects.frequency_band import FrequencyBand
        return FrequencyBand.from_zipf(self.zipf_frequency)

    @property
    def is_sweet_spot(self) -> bool:
        return self.frequency_band.is_sweet_spot
