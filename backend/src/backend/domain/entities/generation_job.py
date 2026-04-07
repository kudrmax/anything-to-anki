from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.generation_job_status import GenerationJobStatus


@dataclass
class GenerationJob:
    """A persistent job for background AI definition generation.

    One job = one batch of candidates (up to 15 words).
    """

    source_id: int | None  # None means "all sources"
    status: GenerationJobStatus
    total_candidates: int
    candidate_ids: list[int]  # Explicit snapshot of candidates for this batch
    processed_candidates: int = 0
    failed_candidates: int = 0
    skipped_candidates: int = 0  # Skipped due to status change (KNOWN/SKIP) during execution
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    id: int | None = None
