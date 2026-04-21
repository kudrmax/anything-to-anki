from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.job_status import JobStatus
    from backend.domain.value_objects.job_type import JobType


@dataclass(frozen=True)
class Job:
    """A unit of work in the queue.

    Each job represents one candidate to process (or one source for video download).
    Meaning generation batching is handled by the worker at dequeue time,
    not in the schema — every meaning job is still one row per candidate.
    """

    id: int | None
    job_type: JobType
    candidate_id: int | None  # None for source-level jobs (VIDEO_DOWNLOAD)
    source_id: int
    status: JobStatus
    error: str | None
    created_at: datetime
    started_at: datetime | None
