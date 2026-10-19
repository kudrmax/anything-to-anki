from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidEarnedSectionError
from backend.domain.services.card_view import is_earnable
from backend.domain.value_objects.card_choice import CardChoice, CardState

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.card_choice import Binding
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

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
    another source, or AI made it. `earned_section`: the section the phrase earned when it was
    added or its text last changed; never Reviewed.
    """

    candidate_id: int
    origin: OccurrenceOrigin
    source_phrase: Phrase
    phrase_position: DocumentPosition | None
    key: OccurrenceKey | None
    fragment_score: float | None
    earned_section: CandidateSection
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

    def __post_init__(self) -> None:
        if not is_earnable(self.earned_section):
            raise InvalidEarnedSectionError(self.earned_section)

    @property
    def card_state(self) -> CardState:
        assert self.id is not None
        return CardState(self.id, self.choice, self.binding)

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
