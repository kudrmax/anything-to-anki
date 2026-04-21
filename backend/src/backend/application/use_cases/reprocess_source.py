from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    SourceHasActiveJobsError,
    SourceNotFoundError,
    SourceNotReprocessableError,
)
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.use_cases.process_source import ProcessSourceUseCase
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.candidate_repository import CandidateRepository
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
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
        process_source_use_case: ProcessSourceUseCase,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo
        self._process_source_uc = process_source_use_case

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _REPROCESSABLE_STATUSES:
            raise SourceNotReprocessableError(source_id)

        if self._has_active_enrichments(source_id):
            raise SourceHasActiveJobsError(source_id)

        logger.info("reprocess_source: deleting candidates (source_id=%d)", source_id)
        self._candidate_repo.delete_by_source(source_id)

        reset = source.reset_to_initial_state()
        self._source_repo.update_source(reset)

        logger.info("reprocess_source: starting pipeline (source_id=%d)", source_id)
        self._process_source_uc.start(source_id)

    def _has_active_enrichments(self, source_id: int) -> bool:
        for repo in (self._meaning_repo, self._media_repo, self._pronunciation_repo):
            for status in (EnrichmentStatus.RUNNING, EnrichmentStatus.QUEUED):
                if repo.get_candidate_ids_by_status(source_id, status):
                    return True
        return False
