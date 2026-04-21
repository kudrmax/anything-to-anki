from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository


@dataclass(frozen=True)
class ReprocessStats:
    learn_count: int
    known_count: int
    skip_count: int
    pending_count: int
    has_active_jobs: bool


class GetReprocessStatsUseCase:
    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo

    def execute(self, source_id: int) -> ReprocessStats:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        candidates = self._candidate_repo.get_by_source(source_id)

        counts: dict[CandidateStatus, int] = {s: 0 for s in CandidateStatus}
        for c in candidates:
            counts[c.status] += 1

        has_active = self._has_active_enrichments(source_id)

        return ReprocessStats(
            learn_count=counts[CandidateStatus.LEARN],
            known_count=counts[CandidateStatus.KNOWN],
            skip_count=counts[CandidateStatus.SKIP],
            pending_count=counts[CandidateStatus.PENDING],
            has_active_jobs=has_active,
        )

    def _has_active_enrichments(self, source_id: int) -> bool:
        for repo in (self._meaning_repo, self._media_repo, self._pronunciation_repo):
            for status in (EnrichmentStatus.RUNNING, EnrichmentStatus.QUEUED):
                if repo.get_candidate_ids_by_status(source_id, status):
                    return True
        return False
