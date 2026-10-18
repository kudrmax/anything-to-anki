from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_choice import DECISION_CHOICES, CardChoice, CardState
from backend.domain.value_objects.phrase_origin_kind import DecisionKind

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.value_objects.card_choice import Binding
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

_DECISION_KIND_OF_CHOICE = {
    CardChoice.LEARN: DecisionKind.LEARN, CardChoice.CLOZE: DecisionKind.CLOZE,
}


@dataclass(frozen=True)
class OccurrenceKey:
    """Where the target starts in the document of its part: stable, layout-independent."""

    block: int
    line: int
    char: int


@dataclass(frozen=True)
class Occurrence:
    """A phrase of a word: the place in the text and everything made for that place.

    The meaning, media, tts, cloze and the active binding are attached by the repository.
    `choice` is the one button chosen on the card; `binding` its active binding to an Anki
    note. `replaces_selection`: the user put this phrase in place of the word's selection
    card, so the selection shows none. `collected_from`: where a collected phrase was found —
    another source, or AI made it.
    """

    candidate_id: int
    origin: OccurrenceOrigin
    source_phrase: Phrase
    phrase_position: DocumentPosition | None
    key: OccurrenceKey | None
    fragment_score: float | None
    revision: int = 0
    shown_by: ShownBy | None = None
    choice: CardChoice = CardChoice.NONE
    edited_by_user: bool = False
    replaces_selection: bool = False
    polished_phrase: Phrase | None = None
    polish_reverted: bool = False
    collected_from: PhraseOrigin | None = None
    id: int | None = None
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    tts: CandidateTTS | None = None
    cloze: CandidateCloze | None = None
    binding: Binding | None = None
    has_active_job: bool = False

    @property
    def card_state(self) -> CardState:
        assert self.id is not None
        return CardState(self.id, self.choice, self.binding)

    # Compatibility until the readers move to `choice` / `in_anki` (plan step 7).
    @property
    def skipped(self) -> bool:
        return self.choice is CardChoice.SKIP

    @property
    def is_decision(self) -> bool:
        return self.choice in DECISION_CHOICES

    @property
    def decision_kind(self) -> DecisionKind | None:
        return _DECISION_KIND_OF_CHOICE.get(self.choice)

    @property
    def exported(self) -> bool:
        """In Anki: the card has an active binding."""
        return self.binding is not None

    @property
    def phrase(self) -> Phrase:
        """The phrase the card shows, speaks and exports."""
        if self.polished_phrase is not None and not self.polish_reverted:
            return self.polished_phrase
        return self.source_phrase

    @property
    def is_shown(self) -> bool:
        return self.shown_by is not None

    @property
    def has_results(self) -> bool:
        """Anything was made for the phrase: polish, meaning, picture or video, audio, cloze."""
        return (
            self.polished_phrase is not None
            or (self.meaning is not None and bool(self.meaning.meaning))
            or (
                self.media is not None
                and (self.media.screenshot_path is not None or self.media.audio_path is not None)
            )
            or (self.tts is not None and self.tts.audio_path is not None)
            or self.cloze is not None
        )
