from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic resolves it at runtime

from pydantic import BaseModel, Field

MAX_COMMENT_LENGTH = 1000


class ReportCandidateRequest(BaseModel):
    """Input for complaining about a card."""

    comment: str = Field(min_length=1, max_length=MAX_COMMENT_LENGTH)


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
    comment: str
    text_before: str | None
    text_after: str | None
    created_at: datetime
