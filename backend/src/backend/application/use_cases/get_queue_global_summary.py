from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import JobTypeSummaryDTO, QueueGlobalSummaryDTO
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import (
        CandidateMeaningRepository,
    )
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.source_repository import SourceRepository


class GetQueueGlobalSummaryUseCase:
    """Aggregate queued/running/failed counts for all 5 job types."""

    def __init__(
        self,
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo
        self._source_repo = source_repo

    def execute(self, source_id: int | None = None) -> QueueGlobalSummaryDTO:
        def _summary(repo: CandidateMeaningRepository | CandidateMediaRepository | CandidatePronunciationRepository) -> JobTypeSummaryDTO:  # noqa: E501
            return JobTypeSummaryDTO(
                queued=repo.count_by_status_global(EnrichmentStatus.QUEUED, source_id=source_id),
                running=repo.count_by_status_global(EnrichmentStatus.RUNNING, source_id=source_id),
                failed=repo.count_by_status_global(EnrichmentStatus.FAILED, source_id=source_id),
            )

        # TODO: youtube_dl and processing counts require source-level job tracking
        # which is not yet implemented in source_repository. Returning zeros for now.
        zero = JobTypeSummaryDTO(queued=0, running=0, failed=0)

        return QueueGlobalSummaryDTO(
            youtube_dl=zero,
            processing=zero,
            meanings=_summary(self._meaning_repo),
            media=_summary(self._media_repo),
            pronunciation=_summary(self._pronunciation_repo),
        )
