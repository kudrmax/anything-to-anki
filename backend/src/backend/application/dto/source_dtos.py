from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO
from backend.domain.value_objects.input_method import InputMethod


class CreateSourceRequest(BaseModel):
    """Input for creating a new text source."""

    raw_text: str
    input_method: InputMethod = InputMethod.TEXT_PASTED
    title: str | None = None


class UpdateTitleRequest(BaseModel):
    """Input for renaming a source."""

    title: str


class SourceDTO(BaseModel):
    """Summary view of a source (for list endpoints)."""

    id: int
    title: str
    raw_text_preview: str
    status: str
    source_type: str
    content_type: str
    source_url: str | None = None
    video_downloaded: bool = False
    created_at: datetime
    candidate_count: int
    learn_count: int
    processing_stage: str | None = None


class CandidateMeaningDTO(BaseModel):
    """Meaning enrichment of a candidate (1:1)."""

    meaning: str | None
    translation: str | None
    synonyms: str | None
    examples: str | None
    ipa: str | None
    status: str  # 'queued' | 'running' | 'done' | 'failed'
    error: str | None
    generated_at: datetime | None


class CandidateMediaDTO(BaseModel):
    """Media enrichment of a candidate (1:1)."""

    screenshot_path: str | None
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    status: str
    error: str | None
    generated_at: datetime | None


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
    is_phrasal_verb: bool = False
    has_custom_context_fragment: bool = False
    meaning: CandidateMeaningDTO | None = None
    media: CandidateMediaDTO | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None


class SourceDetailDTO(BaseModel):
    """Detailed view of a source with candidates."""

    id: int
    title: str
    raw_text: str
    cleaned_text: str | None
    status: str
    source_type: str
    content_type: str
    source_url: str | None = None
    video_downloaded: bool = False
    error_message: str | None
    processing_stage: str | None = None
    created_at: datetime
    candidates: list[StoredCandidateDTO]


SourceDetailDTO.model_rebuild()
