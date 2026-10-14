from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy


@dataclass(frozen=True)
class OccurrenceRow:
    """A light view of a phrase: what deciding about it needs, without its texts and results.

    `text_hash` identifies the source text of the phrase (see `hash_text`); `phrase_hash`
    the source phrase with the facts about its words and its place (see `hash_phrase`).
    `shows_polish`: the card shows the polished phrase, not the source one.
    """

    id: int
    candidate_id: int
    key: OccurrenceKey | None
    origin: OccurrenceOrigin
    shown_by: ShownBy | None
    skipped: bool
    is_decision: bool
    revision: int
    edited_by_user: bool
    has_results: bool
    exported: bool
    has_active_job: bool
    text_hash: str
    fragment_score: float | None
    shows_polish: bool
    phrase_hash: str

    @property
    def is_shown(self) -> bool:
        return self.shown_by is not None

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def hash_phrase(phrase: Phrase, position: DocumentPosition | None) -> str:
        return hashlib.sha256(repr((phrase, position)).encode()).hexdigest()
