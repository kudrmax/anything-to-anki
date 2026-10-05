from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.domain.value_objects.job_type import JobType


@dataclass(frozen=True)
class Job:
    """A unit of work in the queue.

    Each job represents one candidate to process (or one source for source-level
    jobs such as VIDEO_DOWNLOAD and TOPIC_TARGETS). Batching is decided at claim
    time, not in the schema — every job is one row.
    """

    id: int | None
    job_type: JobType
    candidate_id: int | None  # None for source-level jobs
    source_id: int
    status: JobStatus
    error: str | None
    created_at: datetime
    started_at: datetime | None

    @classmethod
    def queued(
        cls, job_type: JobType, source_id: int, candidate_id: int | None = None,
    ) -> Job:
        return cls(
            id=None,
            job_type=job_type,
            candidate_id=candidate_id,
            source_id=source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=datetime.now(tz=UTC),
            started_at=None,
        )
