from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.media_extraction_job import MediaExtractionJob
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extraction_job_repository import MediaExtractionJobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class StartMediaExtractionUseCase:
    """Creates a MediaExtractionJob for all eligible LEARN candidates of a source."""

    def __init__(
        self,
        job_repo: MediaExtractionJobRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo

    def execute(self, source_id: int) -> MediaExtractionJob:
        candidates = self._candidate_repo.get_by_source(source_id)
        eligible = [
            c for c in candidates
            if c.status == CandidateStatus.LEARN
            and c.media_start_ms is not None
            and c.media_end_ms is not None
            and c.screenshot_path is None
            and c.id is not None
        ]
        learn_count = sum(1 for c in candidates if c.status == CandidateStatus.LEARN)
        logger.info(
            "StartMediaExtraction source=%d: %d total, %d learn, %d eligible",
            source_id, len(candidates), learn_count, len(eligible),
        )
        job = MediaExtractionJob(
            source_id=source_id,
            status=MediaExtractionJobStatus.PENDING,
            total_candidates=len(eligible),
            candidate_ids=[c.id for c in eligible],  # type: ignore[misc]
        )
        return self._job_repo.create(job)


class GetMediaExtractionStatusUseCase:
    """Returns status of the latest media extraction job for a source."""

    def __init__(self, job_repo: MediaExtractionJobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, job_id: int) -> MediaExtractionJob | None:
        return self._job_repo.get_by_id(job_id)
