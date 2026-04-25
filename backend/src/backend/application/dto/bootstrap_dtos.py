from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class BootstrapStatusDTO(BaseModel):
    """Status of the bootstrap calibration data."""

    status: str
    error: str | None
    built_at: datetime | None
    word_count: int


class BootstrapWordDTO(BaseModel):
    """A word for the bootstrap calibration screen."""

    lemma: str
    cefr_level: str
    zipf_value: float


class GetBootstrapWordsRequest(BaseModel):
    """Request for bootstrap words with exclusion list."""

    excluded: list[str] = []


class SaveBootstrapWordsRequest(BaseModel):
    """Request to save bootstrap words as known."""

    lemmas: list[str]
