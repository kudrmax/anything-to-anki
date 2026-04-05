from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel

from backend.domain.value_objects.source_type import SourceType


class CreateSourceRequest(BaseModel):
    """Input for creating a new text source."""

    raw_text: str
    source_type: SourceType = SourceType.TEXT


class SourceDTO(BaseModel):
    """Summary view of a source (for list endpoints)."""

    id: int
    raw_text_preview: str
    status: str
    source_type: str
    created_at: datetime
    candidate_count: int
    learn_count: int


class SourceDetailDTO(BaseModel):
    """Detailed view of a source with candidates."""

    id: int
    raw_text: str
    cleaned_text: str | None
    status: str
    source_type: str
    error_message: str | None
    created_at: datetime
    candidates: list[StoredCandidateDTO]


class StoredCandidateDTO(BaseModel):
    """A persisted word candidate."""

    id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    fragment_purity: str
    occurrences: int
    status: str
    surface_form: str | None = None
    ai_meaning: str | None = None
    definition: str | None = None
    ipa: str | None = None
    is_phrasal_verb: bool = False


SourceDetailDTO.model_rebuild()
