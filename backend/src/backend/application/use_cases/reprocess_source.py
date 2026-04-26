from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    SourceHasActiveJobsError,
    SourceNotFoundError,
    SourceNotReprocessableError,
)
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.use_cases.process_source import ProcessSourceUseCase
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.enrichment_cache_repository import EnrichmentCacheRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)

_REPROCESSABLE_STATUSES = frozenset({
    SourceStatus.DONE,
    SourceStatus.PARTIALLY_REVIEWED,
    SourceStatus.REVIEWED,
    SourceStatus.ERROR,
})


class ReprocessSourceUseCase:
    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        job_repo: JobRepository,
        process_source_use_case: ProcessSourceUseCase,
        enrichment_cache_repo: EnrichmentCacheRepository | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo
        self._process_source_uc = process_source_use_case
        self._enrichment_cache_repo = enrichment_cache_repo

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _REPROCESSABLE_STATUSES:
            raise SourceNotReprocessableError(source_id)

        if self._job_repo.has_active_jobs_for_source(source_id):
            raise SourceHasActiveJobsError(source_id)

        if self._enrichment_cache_repo is not None:
            logger.info("reprocess_source: saving enrichment to cache (source_id=%d)", source_id)
            self._enrichment_cache_repo.save_from_source(source_id)

        logger.info("reprocess_source: deleting candidates (source_id=%d)", source_id)
        self._candidate_repo.delete_by_source(source_id)

        reset = source.reset_to_initial_state()
        self._source_repo.update_source(reset)

        logger.info("reprocess_source: starting pipeline (source_id=%d)", source_id)
        self._process_source_uc.start(source_id)

    def finalize(self, source_id: int) -> None:
        """Restore enrichment from cache for matching candidates. Best-effort."""
        if self._enrichment_cache_repo is None:
            return
        try:
            restored = self._enrichment_cache_repo.restore_to_candidates(source_id)
            self._enrichment_cache_repo.cleanup(source_id)
            logger.info(
                "enrichment restore: %d candidates restored (source_id=%d)",
                restored, source_id,
            )
        except Exception:
            logger.warning(
                "enrichment restore failed (source_id=%d), continuing without",
                source_id,
                exc_info=True,
            )
