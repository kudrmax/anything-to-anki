from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.application.utils.anki_note_types import NoteTypeCheck


class NoteTypeCheckDTO(BaseModel):
    """How a note type stands in Anki.

    `fix` is what makes it able to take the cards: `create` when it is not in
    Anki, `add_fields` when it lacks fields the export fills; None when ready.
    """

    kind: str
    note_type: str
    exists: bool
    missing_fields: list[str]
    fix: str | None

    @staticmethod
    def of(check: NoteTypeCheck) -> NoteTypeCheckDTO:
        return NoteTypeCheckDTO(
            kind=check.kind.value,
            note_type=check.note_type,
            exists=check.exists,
            missing_fields=list(check.missing_fields),
            fix=check.fix.value if check.fix else None,
        )


class AnkiStatusDTO(BaseModel):
    """AnkiConnect availability, and the user's note types that would lose parts of cards."""

    available: bool
    version: int | None = None
    note_type_problems: list[NoteTypeCheckDTO] = []


class CardPreviewDTO(BaseModel):
    """Preview of a generated Anki card."""

    candidate_id: int
    lemma: str
    sentence: str        # card phrase with <b>word</b>; for a cloze card the hidden words in <b>
    meaning: str | None  # None if not yet fetched from dictionary
    translation: str | None = None
    synonyms: str | None = None
    examples: str | None = None
    ipa: str | None = None
    screenshot_url: str | None = None
    audio_url: str | None = None
    pronunciation_us_url: str | None = None
    pronunciation_uk_url: str | None = None
    tts_audio_url: str | None = None
    missing: list[str] = []  # required parts the card lacks: 'meaning', 'audio'
    is_cloze: bool = False


class ExportSectionDTO(BaseModel):
    """A group of cards from one source, for the export page."""

    source_id: int
    source_title: str
    cards: list[CardPreviewDTO]


class GlobalExportDTO(BaseModel):
    """Cards still waiting for export: ready ones and incomplete ones, each grouped by source."""

    ready: list[ExportSectionDTO]
    incomplete: list[ExportSectionDTO]
    exported_count: int = 0  # 'learn' cards in scope that are already in Anki


class SyncResultDTO(BaseModel):
    """Result of a sync-to-anki operation."""

    total: int
    added: int
    skipped: int   # rejected by Anki as duplicates of notes already in the deck
    errors: int
    skipped_lemmas: list[str] = []
    error_lemmas: list[str] = []


class AnkiTemplatesDTO(BaseModel):
    """Rendered card templates of both note types with user field names substituted.

    `front`/`back` belong to the recognition note type, `cloze_front`/`cloze_back`
    to the cloze one; both share `css`.
    """

    front: str
    back: str
    cloze_front: str
    cloze_back: str
    css: str
