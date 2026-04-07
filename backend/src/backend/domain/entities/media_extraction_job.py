from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus


@dataclass
class MediaExtractionJob:
    """A batch job for extracting screenshots and audio clips from a video source."""

    source_id: int | None
    status: MediaExtractionJobStatus
    total_candidates: int
    candidate_ids: list[int]
    processed_candidates: int = 0
    failed_candidates: int = 0
    skipped_candidates: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    id: int | None = None
