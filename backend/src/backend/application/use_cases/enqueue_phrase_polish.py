from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    CandidateNotFoundError,
    PhrasePolishNotSupportedError,
    SourceNotFoundError,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)

POLISH_BATCH_SIZE = 15
_ACTIVE_STATUSES = frozenset({CandidateStatus.PENDING, CandidateStatus.LEARN})


class EnqueuePhrasePolishUseCase:
    """Queues AI polishing of card phrases: for a whole source or for one card again."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> int:
        """Queue every active card whose phrase AI has not looked at yet. Returns how many."""
        source = self._polishable_source(source_id)
        waiting = [
            c for c in self._candidate_repo.get_by_source(source_id)
            if c.status in _ACTIVE_STATUSES and c.polished_fragment is None
        ]
        ordered = self._candidate_sorter.sort(waiting, source, sort_order)
        queued = self._queue(source_id, ordered)
        logger.info(
            "enqueue_phrase_polish: queued (source_id=%d, total=%d, sort_order=%s)",
            source_id, queued, sort_order.value,
        )
        return queued

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

    def _queue(self, source_id: int, candidates: list[StoredCandidate]) -> int:
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
        return len(jobs)
