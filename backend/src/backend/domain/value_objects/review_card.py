from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.elsewhere import Elsewhere
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.phrase import Phrase


def card_is_done(word_status: WordStatus, skipped: bool, elsewhere: Elsewhere | None) -> bool:
    """A card is done when its word is decided, its phrase skipped, or the word is known or
    learned via another source."""
    return word_status is not WordStatus.PENDING or skipped or elsewhere is not None


@dataclass(frozen=True)
class ReviewCard:
    """A card of the review list: one shown phrase of a word, with everything made for it.

    `word_status`: the decision on the word. `elsewhere`: why the word, still open here,
    counts as done via another source.
    """

    word: StoredCandidate
    occurrence: Occurrence
    word_status: WordStatus
    elsewhere: Elsewhere | None = None

    @property
    def word_id(self) -> int:
        assert self.word.id is not None
        return self.word.id

    @property
    def phrase_id(self) -> int:
        assert self.occurrence.id is not None
        return self.occurrence.id

    @property
    def lemma(self) -> str:
        return self.word.lemma

    @property
    def pos(self) -> str:
        return self.word.pos

    @property
    def zipf_frequency(self) -> float:
        return self.word.zipf_frequency

    @property
    def frequency_band(self) -> FrequencyBand:
        return self.word.frequency_band

    @property
    def phrase(self) -> Phrase:
        """The phrase the card shows."""
        return self.occurrence.phrase

    @property
    def skipped(self) -> bool:
        return self.occurrence.skipped

    @property
    def is_done(self) -> bool:
        return card_is_done(self.word_status, self.skipped, self.elsewhere)

    @property
    def shown_status(self) -> CandidateStatus:
        """The decision the card shows: the word's, which beats a Skip of the phrase."""
        if self.word_status is not WordStatus.PENDING:
            return CandidateStatus(self.word_status.value)
        return CandidateStatus.SKIP if self.skipped else CandidateStatus.PENDING


@dataclass(frozen=True)
class CardRow:
    """A card as the lists of sources need it: the word's facts and the shown text, light."""

    source_id: int
    word_id: int
    phrase_id: int
    lemma: str
    pos: str
    zipf_frequency: float
    word_status: WordStatus
    skipped: bool
    phrase: Phrase
    elsewhere: Elsewhere | None = None

    @property
    def is_done(self) -> bool:
        return card_is_done(self.word_status, self.skipped, self.elsewhere)
