from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

BATCH_SIZE = 15


class EnqueueMeaningGenerationUseCase:
    """Finds all active candidates without meaning, marks them QUEUED, returns batches of 15.

    The order of returned batches respects sort_order — first batch contains the
    highest-priority candidates so they're processed first by the worker.
    """

    def __init__(self, meaning_repo: CandidateMeaningRepository) -> None:
        self._meaning_repo = meaning_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[list[int]]:
        all_ids = self._meaning_repo.get_candidate_ids_without_meaning(
            source_id=source_id,
            only_active=True,
            sort_order=sort_order,
        )
        if not all_ids:
            return []
        self._meaning_repo.mark_queued_bulk(all_ids)
        return [all_ids[i:i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
