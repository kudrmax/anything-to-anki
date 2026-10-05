from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository


class EnqueueCandidateTTSUseCase:
    """Queues TTS for one card; a card already waiting for TTS is not queued twice."""

    def __init__(self, candidate_repo: CandidateRepository, job_repo: JobRepository) -> None:
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo

    def execute(self, candidate_id: int) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        self._job_repo.enqueue([Job.queued(JobType.TTS, candidate.source_id, candidate_id)])
