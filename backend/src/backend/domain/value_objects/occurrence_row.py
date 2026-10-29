from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_choice import CardState
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.user_work import UserWork

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.card_choice import Binding, CardChoice
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_generation import PhraseGeneration


@dataclass(frozen=True)
class OccurrenceRow:
    """A light view of a phrase: what deciding about it needs, without its texts and results.

    `text_hash` identifies the source text of the phrase (see `hash_text`); `phrase_hash`
    the source phrase with the facts about its words and its place (see `hash_phrase`).
    `shows_polish`: the card shows the polished phrase, not the source one.
    `generation`: what was made for the phrase.
    `replaces_selection`: the phrase took the place of the word's selection card.
    `removed_by_user`: the user removed the card of the phrase.
    `binding`: the card's active binding to an Anki note. `source_phrase`: the phrase cut from
    the source; `shown_phrase`: the phrase the card shows. `earned_section`: the section
    stored on the phrase.
    """

    id: int
    candidate_id: int
    key: OccurrenceKey | None
    origin: OccurrenceOrigin
    shown_by: ShownBy | None
    choice: CardChoice
    revision: int
    edited_by_user: bool
    generation: PhraseGeneration
    binding: Binding | None
    has_active_job: bool
    text_hash: str
    fragment_score: float | None
    shows_polish: bool
    phrase_hash: str
    source_phrase: Phrase
    shown_phrase: Phrase
    earned_section: CandidateSection
    replaces_selection: bool = False
    removed_by_user: bool = False

    @property
    def is_shown(self) -> bool:
        return self.shown_by is not None

    @property
    def card_state(self) -> CardState:
        return CardState(self.id, self.choice, self.binding)

    @property
    def user_work(self) -> UserWork:
        return UserWork(
            edited=self.edited_by_user,
            picked=self.shown_by is ShownBy.USER,
            added=self.origin is not OccurrenceOrigin.AUTO,
            removed=self.removed_by_user,
        )

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def hash_phrase(phrase: Phrase, position: DocumentPosition | None) -> str:
        return hashlib.sha256(repr((phrase, position)).encode()).hexdigest()
