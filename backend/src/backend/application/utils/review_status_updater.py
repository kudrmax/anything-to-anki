from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import derive_review_status

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository


class ReviewStatusUpdater:
    """Пересчитывает статус ревью источника после изменения его кандидатов."""

    def __init__(self, source_repo: SourceRepository, candidate_repo: CandidateRepository) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo

    def refresh(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return
        candidates = self._candidate_repo.get_by_source(source_id)
        statuses = (candidate.status for candidate in candidates)
        status = derive_review_status(source.status, statuses)
        if status != source.status:
            self._source_repo.update_status(source_id, status)
