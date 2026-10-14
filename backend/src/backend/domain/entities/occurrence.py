from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import (
        DecisionKind,
        OccurrenceOrigin,
        ShownBy,
    )


@dataclass(frozen=True)
class OccurrenceKey:
    """Where the target starts in the document of its part: stable, layout-independent."""

    block: int
    line: int
    char: int


@dataclass(frozen=True)
class Occurrence:
    """A phrase of a word: the place in the text and everything made for that place.

    The meaning, media, tts and cloze are attached by the repository.
    `exported` means a row of `anki_synced_cards` points here.
    """

    candidate_id: int
    origin: OccurrenceOrigin
    source_phrase: Phrase
    phrase_position: DocumentPosition | None
    key: OccurrenceKey | None
    fragment_score: float | None
    revision: int = 0
    shown_by: ShownBy | None = None
    skipped: bool = False
    is_decision: bool = False
    decision_kind: DecisionKind | None = None
    edited_by_user: bool = False
    polished_phrase: Phrase | None = None
    polish_reverted: bool = False
    id: int | None = None
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    tts: CandidateTTS | None = None
    cloze: CandidateCloze | None = None
    exported: bool = False
    has_active_job: bool = False

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
