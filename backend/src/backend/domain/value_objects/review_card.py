from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.card_view import card_is_done, card_view
from backend.domain.value_objects.card_choice import is_skipped

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.services.card_view import CardView
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.elsewhere import ElsewhereStatus
    from backend.domain.value_objects.frequency_band import FrequencyBand
    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.word_status import WordStatus


@dataclass(frozen=True)
class CardContext:
    """What the decision tables read for a card: every card of its word, what the user
    knows of the lemma, and the request's moment."""

    word: WordState
    knowledge: LemmaKnowledge
    now: datetime


@dataclass(frozen=True)
class ReviewCard:
    """A card of the review list: one shown phrase of a word, with everything made for it.

    `elsewhere`: why the word, still open here, counts as done via another source.
    `context`: what the card view is derived from; a card only sorted needs none.
    """

    word: StoredCandidate
    occurrence: Occurrence
    elsewhere: ElsewhereStatus | None = None
    context: CardContext | None = None

    @property
    def view(self) -> CardView:
        context = self.context
        assert context is not None, "a card shown to the user is read with its context"
        return card_view(
            context.word, self.phrase_id, context.knowledge, self.elsewhere, context.now,
        )

    @property
    def word_status(self) -> WordStatus:
        """The decision on the word."""
        return self.word.status

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
    def earned_section(self) -> CandidateSection:
        return self.occurrence.earned_section

    @property
    def skipped(self) -> bool:
        return is_skipped(self.occurrence.card_state)

    @property
    def is_done(self) -> bool:
        return card_is_done(self.word_status, self.skipped, self.elsewhere)


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
    earned_section: CandidateSection
    elsewhere: ElsewhereStatus | None = None

    @property
    def is_done(self) -> bool:
        return card_is_done(self.word_status, self.skipped, self.elsewhere)
