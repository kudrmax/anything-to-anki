from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository

BATCH_SIZE = 15


class EnqueueMeaningGenerationUseCase:
    """Finds all active candidates without meaning, marks them QUEUED, returns batches of 15."""

    def __init__(self, meaning_repo: CandidateMeaningRepository) -> None:
        self._meaning_repo = meaning_repo

    def execute(self, source_id: int) -> list[list[int]]:
        all_ids = self._meaning_repo.get_candidate_ids_without_meaning(
            source_id=source_id, only_active=True,
        )
        if not all_ids:
            return []
        self._meaning_repo.mark_queued_bulk(all_ids)
        return [all_ids[i:i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
