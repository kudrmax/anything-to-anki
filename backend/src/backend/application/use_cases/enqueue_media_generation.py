from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class EnqueueMediaGenerationUseCase:
    """Finds eligible candidates for a source, creates Job rows, returns their ids."""

    def __init__(
        self,
        media_repo: CandidateMediaRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
    ) -> None:
        self._media_repo = media_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[int]:
        unsorted_ids = self._media_repo.get_eligible_candidate_ids(source_id=source_id)
        if not unsorted_ids:
            return []
        candidates = self._candidate_repo.get_by_ids(unsorted_ids)
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return []
        candidates = self._candidate_sorter.sort(candidates, source, sort_order)
        eligible_ids = [c.id for c in candidates if c.id is not None]
        if not eligible_ids:
            logger.info(
                "enqueue_media_generation: no eligible candidates "
                "(source_id=%d, sort_order=%s)",
                source_id, sort_order.value,
            )
            return []

        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                id=None,
                job_type=JobType.MEDIA,
                candidate_id=cid,
                source_id=source_id,
                status=JobStatus.QUEUED,
                error=None,
                created_at=now,
                started_at=None,
            )
            for cid in eligible_ids
        ]
        self._job_repo.create_bulk(jobs)

        logger.info(
            "enqueue_media_generation: queued (source_id=%d, count=%d, sort_order=%s)",
            source_id, len(eligible_ids),
            sort_order.value,
        )
        return eligible_ids
