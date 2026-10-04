from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    CandidateNotFoundError,
    PhrasePolishNotSupportedError,
    SourceNotFoundError,
)
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class EnqueuePhrasePolishUseCase:
    """Queues AI polishing of one card's phrase again; whole sources go through RunGeneration."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        job_repo: JobRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._job_repo = job_repo

    def execute_one(self, candidate_id: int) -> None:
        """Polish one card's phrase again from its source phrase."""
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        self._polishable_source(candidate.source_id)
        self._candidate_repo.set_polished_fragment(candidate.id, None)
        self._queue(candidate.source_id, [candidate])

    def _polishable_source(self, source_id: int) -> Source:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if not source.can_polish_phrases:
            raise PhrasePolishNotSupportedError(source_id)
        return source

    def _queue(self, source_id: int, candidates: list[StoredCandidate]) -> None:
        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                id=None,
                job_type=JobType.POLISH,
                candidate_id=c.id,
                source_id=source_id,
                status=JobStatus.QUEUED,
                error=None,
                created_at=now,
                started_at=None,
            )
            for c in candidates
            if c.id is not None
        ]
        if jobs:
            self._job_repo.create_bulk(jobs)
