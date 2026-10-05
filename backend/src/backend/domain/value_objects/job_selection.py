from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.job_type import JobType

UNKNOWN_JOB_ERROR = "Unknown error"


@dataclass(frozen=True)
class JobSelection:
    """Which jobs a queue action applies to. Every unset field matches everything.

    ``error`` matches the job's error text exactly; UNKNOWN_JOB_ERROR also
    matches jobs that failed without one.
    """

    job_type: JobType | None = None
    source_id: int | None = None
    job_id: int | None = None
    error: str | None = None
