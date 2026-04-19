from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


class EnqueueMediaGenerationUseCase:
    """Finds eligible candidates for a source, marks them QUEUED, returns their ids.
    The actual Redis enqueue happens in the FastAPI route (async context).

    The order of returned ids respects sort_order. Sorting is delegated to
    domain sort service.
    """

    def __init__(
        self,
        media_repo: CandidateMediaRepository,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._media_repo = media_repo
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[int]:
        from backend.domain.services.candidate_sorting import (
            sort_by_relevance,
            sort_chronologically,
        )
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        unsorted_ids = self._media_repo.get_eligible_candidate_ids(source_id=source_id)
        if not unsorted_ids:
            return []
        candidates = self._candidate_repo.get_by_ids(unsorted_ids)
        if sort_order == SortEnum.CHRONOLOGICAL:
            source = self._source_repo.get_by_id(source_id)
            if source is None:
                return []
            text = source.cleaned_text or source.raw_text
            candidates = sort_chronologically(candidates, source_text=text)
        else:
            candidates = sort_by_relevance(candidates)
        eligible_ids = [c.id for c in candidates if c.id is not None]
        if not eligible_ids:
            logger.info(
                "enqueue_media_generation: no eligible candidates "
                "(source_id=%d, sort_order=%s)",
                source_id, sort_order.value if sort_order else None,
            )
            return []
        self._media_repo.mark_queued_bulk(eligible_ids)
        logger.info(
            "enqueue_media_generation: queued (source_id=%d, count=%d, sort_order=%s)",
            source_id, len(eligible_ids),
            sort_order.value if sort_order else None,
        )
        return eligible_ids
