from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)

BATCH_SIZE = 15


class EnqueueMeaningGenerationUseCase:
    """Finds all active candidates without meaning, creates Job rows, returns batches of 15.

    The order of returned batches respects sort_order so the worker processes
    them in the user's chosen order. Sorting is delegated to domain sort service.
    """

    def __init__(
        self,
        meaning_repo: CandidateMeaningRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[list[int]]:
        unsorted_ids = self._meaning_repo.get_candidate_ids_without_meaning(
            source_id=source_id, only_active=True,
        )
        if not unsorted_ids:
            return []
        candidates = self._candidate_repo.get_by_ids(unsorted_ids)
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return []
        candidates = self._candidate_sorter.sort(candidates, source, sort_order)
        all_ids = [c.id for c in candidates if c.id is not None]
        if not all_ids:
            logger.info(
                "enqueue_meaning_generation: no candidates without meaning "
                "(source_id=%d, sort_order=%s)",
                source_id, sort_order.value,
            )
            return []

        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                id=None,
                job_type=JobType.MEANING,
                candidate_id=cid,
                source_id=source_id,
                status=JobStatus.QUEUED,
                error=None,
                created_at=now,
                started_at=None,
            )
            for cid in all_ids
        ]
        self._job_repo.create_bulk(jobs)

        batches = [all_ids[i:i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
        logger.info(
            "enqueue_meaning_generation: queued (source_id=%d, total=%d, batches=%d, "
            "sort_order=%s)",
            source_id, len(all_ids), len(batches),
            sort_order.value,
        )
        return batches
