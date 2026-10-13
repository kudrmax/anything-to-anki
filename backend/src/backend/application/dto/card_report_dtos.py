from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic resolves it at runtime

from pydantic import BaseModel, Field

MAX_COMMENT_LENGTH = 1000


class PhraseSpan(BaseModel):
    """Characters [start, end) of the card's phrase."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class ReportCandidateRequest(BaseModel):
    """Input for complaining about a card: quick reasons, own words, or both.

    `unknown_words` — the words of the phrase the user doesn't know, besides the target.
    """

    reasons: list[str] = Field(default_factory=list)
    comment: str = Field(default="", max_length=MAX_COMMENT_LENGTH)
    unknown_words: list[PhraseSpan] = Field(default_factory=list)


class CardReportDTO(BaseModel):
    """A complaint about a card with the card as it was."""

    id: int
    source_id: int
    source_title: str
    candidate_id: int
    lemma: str
    surface_form: str | None
    context_fragment: str
    zipf_frequency: float
    cefr_level: str | None
    fragment_unknown_count: int
    is_phrasal_verb: bool
    reasons: list[str]
    comment: str
    text_before: str | None
    text_after: str | None
    created_at: datetime
