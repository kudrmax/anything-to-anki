"""What a card offers about its meaning before the meaning text is there."""
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning


class MeaningAction(StrEnum):
    GENERATE = "generate"
    RETRY = "retry"


def meaning_action(
    meaning: CandidateMeaning | None, job_status: JobStatus | None,
) -> MeaningAction | None:
    """Nothing while the meaning is there or being made; a retry after a failed job."""
    if (meaning is not None and meaning.meaning) or job_status is JobStatus.RUNNING:
        return None
    if job_status is JobStatus.FAILED:
        return MeaningAction.RETRY
    return MeaningAction.GENERATE
