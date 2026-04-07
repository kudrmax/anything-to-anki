from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.media_extraction_job import MediaExtractionJob
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.media_extraction_job_repository import MediaExtractionJobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class StartMediaExtractionUseCase:
    """Creates a MediaExtractionJob for all PENDING/LEARN candidates of a source
    that have timecodes in candidate_media but no screenshot yet."""

    def __init__(
        self,
        job_repo: MediaExtractionJobRepository,
        media_repo: CandidateMediaRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._job_repo = job_repo
        self._media_repo = media_repo
        self._source_repo = source_repo

    def execute(self, source_id: int) -> MediaExtractionJob:
        eligible_ids = self._media_repo.get_eligible_candidate_ids(source_id=source_id)
        logger.info(
            "StartMediaExtraction source=%d: %d eligible",
            source_id, len(eligible_ids),
        )
        job = MediaExtractionJob(
            source_id=source_id,
            status=MediaExtractionJobStatus.PENDING,
            total_candidates=len(eligible_ids),
            candidate_ids=eligible_ids,
        )
        return self._job_repo.create(job)


class GetMediaExtractionStatusUseCase:
    """Returns status of the latest media extraction job for a source."""

    def __init__(self, job_repo: MediaExtractionJobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, job_id: int) -> MediaExtractionJob | None:
        return self._job_repo.get_by_id(job_id)
