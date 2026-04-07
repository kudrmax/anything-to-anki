from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


class EnqueueMediaGenerationUseCase:
    """Finds eligible candidates for a source, marks them QUEUED, returns their ids.
    The actual Redis enqueue happens in the FastAPI route (async context).

    The order of returned ids respects sort_order. RELEVANCE uses SQL sort
    on the media repo; CHRONOLOGICAL re-sorts in Python by context_fragment
    position in source text.
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
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        if sort_order == SortEnum.CHRONOLOGICAL:
            unsorted_ids = self._media_repo.get_eligible_candidate_ids(source_id=source_id)
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
            eligible_ids = [c.id for c in candidates if c.id is not None]
        else:
            eligible_ids = self._media_repo.get_eligible_candidate_ids(
                source_id=source_id,
                sort_order=sort_order,
            )
        if not eligible_ids:
            return []
        self._media_repo.mark_queued_bulk(eligible_ids)
        return eligible_ids
