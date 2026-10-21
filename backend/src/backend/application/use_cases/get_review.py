from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import INITIALLY_SHOWN_CANDIDATES
from backend.application.dto.source_dtos import ReviewDTO
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.review_header import ReviewHeader
    from backend.domain.value_objects.source_scope import SourceScope


class GetReviewUseCase:
    """The review screen of a set of sources: its cards in review order, and how far the
    review of the whole set has got, as its header reads it."""

    def __init__(self, card_views: CardViews, header: ReviewHeader) -> None:
        self._card_views = card_views
        self._header = header

    def execute(
        self,
        scope: SourceScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> ReviewDTO:
        listing = self._card_views.listed(scope, sort_order)
        header = self._header.of(scope)
        return ReviewDTO(
            scope=header.scope,
            title=header.title,
            status=header.status,
            progress=header.progress,
            learn_count=header.learn_count,
            candidates=listing.cards,
            initially_shown_candidates=(
                None if sort_order == CandidateSortOrder.CHRONOLOGICAL
                else INITIALLY_SHOWN_CANDIDATES
            ),
            busy=header.busy,
        )
