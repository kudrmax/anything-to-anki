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
    ipa: str | None


class SyncResultDTO(BaseModel):
    """Result of a sync-to-anki operation."""

    total: int
    added: int
    skipped: int   # duplicates already in Anki
    errors: int
    skipped_lemmas: list[str] = []
    error_lemmas: list[str] = []
