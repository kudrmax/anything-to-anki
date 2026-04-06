from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StartGenerationRequest(BaseModel):
    """Request to start background definition generation."""

    source_id: int | None = None  # None = all sources


class GenerationJobDTO(BaseModel):
    """Status view of a generation job (one batch)."""

    id: int
    source_id: int | None
    status: str
    total_candidates: int
    processed_candidates: int
    failed_candidates: int
    skipped_candidates: int
    candidate_ids: list[int]
    created_at: datetime


class GenerationQueueDTO(BaseModel):
    """Complete state of the generation queue."""

    running_job: GenerationJobDTO | None
    pending_jobs: list[GenerationJobDTO]
    total_pending_count: int
