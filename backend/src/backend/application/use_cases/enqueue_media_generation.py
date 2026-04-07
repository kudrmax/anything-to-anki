from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository


class EnqueueMediaGenerationUseCase:
    """Finds eligible candidates for a source, marks them QUEUED, returns their ids.
    The actual Redis enqueue happens in the FastAPI route (async context).
    """

    def __init__(self, media_repo: CandidateMediaRepository) -> None:
        self._media_repo = media_repo

    def execute(self, source_id: int) -> list[int]:
        eligible_ids = self._media_repo.get_eligible_candidate_ids(source_id=source_id)
        if not eligible_ids:
            return []
        self._media_repo.mark_queued_bulk(eligible_ids)
        return eligible_ids
