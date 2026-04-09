from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

logger = logging.getLogger(__name__)

BATCH_SIZE = 15


class EnqueueMeaningGenerationUseCase:
    """Finds all active candidates without meaning, marks them QUEUED, returns batches of 15.

    The order of returned batches respects sort_order so the worker processes
    them in the user's chosen order. RELEVANCE uses SQL sort on the meaning repo;
    CHRONOLOGICAL re-sorts in Python by context_fragment position in source text.
    """

    def __init__(
        self,
        meaning_repo: CandidateMeaningRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[list[int]]:
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        if sort_order == SortEnum.CHRONOLOGICAL:
            # Fetch ids unsorted, then re-sort by position in source text
            unsorted_ids = self._meaning_repo.get_candidate_ids_without_meaning(
                source_id=source_id, only_active=True,
            )
            if not unsorted_ids:
                return []
            source = self._source_repo.get_by_id(source_id)
            if source is None:
                return []
            candidates = self._candidate_repo.get_by_ids(unsorted_ids)
            text = source.cleaned_text or source.raw_text
            candidates.sort(
                key=lambda c: (text.find(c.context_fragment), c.id or 0),
            )
            all_ids = [c.id for c in candidates if c.id is not None]
        else:
            all_ids = self._meaning_repo.get_candidate_ids_without_meaning(
                source_id=source_id,
                only_active=True,
                sort_order=sort_order,
            )
        if not all_ids:
            logger.info(
                "enqueue_meaning_generation: no candidates without meaning "
                "(source_id=%d, sort_order=%s)",
                source_id, sort_order.value if sort_order else None,
            )
            return []
        self._meaning_repo.mark_queued_bulk(all_ids)
        batches = [all_ids[i:i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
        logger.info(
            "enqueue_meaning_generation: queued (source_id=%d, total=%d, batches=%d, "
            "sort_order=%s)",
            source_id, len(all_ids), len(batches),
            sort_order.value if sort_order else None,
        )
        return batches
