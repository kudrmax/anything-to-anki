from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


class EnqueueMediaGenerationUseCase:
    """Finds eligible candidates for a source, marks them QUEUED, returns their ids.
    The actual Redis enqueue happens in the FastAPI route (async context).

    The order of returned ids respects sort_order — first id is the highest priority.
    """

    def __init__(self, media_repo: CandidateMediaRepository) -> None:
        self._media_repo = media_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[int]:
        eligible_ids = self._media_repo.get_eligible_candidate_ids(
            source_id=source_id,
            sort_order=sort_order,
        )
        if not eligible_ids:
            return []
        self._media_repo.mark_queued_bulk(eligible_ids)
        return eligible_ids
