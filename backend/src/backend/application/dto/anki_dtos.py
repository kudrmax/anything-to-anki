from __future__ import annotations

from pydantic import BaseModel


class AnkiStatusDTO(BaseModel):
    """AnkiConnect availability status."""

    available: bool
    version: int | None = None


class CardPreviewDTO(BaseModel):
    """Preview of a generated Anki card."""

    candidate_id: int
    lemma: str
    sentence: str        # context_fragment with <b>word</b>
    meaning: str | None  # None if not yet fetched from dictionary
    translation: str | None = None
    synonyms: str | None = None
    examples: str | None = None
    ipa: str | None = None
    screenshot_url: str | None = None
    audio_url: str | None = None


class SyncResultDTO(BaseModel):
    """Result of a sync-to-anki operation."""

    total: int
    added: int
    skipped: int   # already in anki_synced_cards (previously synced successfully)
    errors: int
    skipped_lemmas: list[str] = []
    error_lemmas: list[str] = []


class VerifyNoteTypeRequest(BaseModel):
    """Request to verify that a note type exists and has required fields."""

    note_type: str
    required_fields: list[str]


class VerifyNoteTypeResponseDTO(BaseModel):
    """Result of note type verification."""

    valid: bool
    available_fields: list[str]
    missing_fields: list[str]


class CreateNoteTypeRequest(BaseModel):
    """Request to create a note type in Anki."""

    note_type: str
    fields: list[str]


class CreateNoteTypeResponseDTO(BaseModel):
    """Result of note type creation."""

    already_existed: bool


class AnkiTemplatesDTO(BaseModel):
    """Rendered Anki card templates with user field names substituted."""

    front: str
    back: str
    css: str
