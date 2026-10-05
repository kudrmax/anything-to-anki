from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.job_type import JobType


@dataclass(frozen=True)
class FailedJobGroup:
    """Failed jobs of one type that share one error."""

    job_type: JobType
    error: str
    count: int
    source_counts: dict[int, int]  # source id -> failed jobs of this group in it

    @property
    def source_ids(self) -> list[int]:
        return sorted(self.source_counts)
