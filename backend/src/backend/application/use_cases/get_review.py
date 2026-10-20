from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import INITIALLY_SHOWN_CANDIDATES
from backend.application.dto.source_dtos import ProgressDTO, ReviewDTO
from backend.domain.services.source_review_status import (
    derive_review_status,
    stored_status_of_set,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.value_objects.source_scope import SourceScope


class GetReviewUseCase:
    """The review screen of a set of sources: its cards in review order, and how far the
    review of the whole set has got."""

    def __init__(
        self,
        card_views: CardViews,
        scope_resolver: SourceScopeResolver,
        card_query: CardQuery,
    ) -> None:
        self._card_views = card_views
        self._scope_resolver = scope_resolver
        self._card_query = card_query

    def execute(
        self,
        scope: SourceScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> ReviewDTO:
        listing = self._card_views.listed(scope, sort_order)
        ids = [s.id for s in listing.sources if s.id is not None]
        return ReviewDTO(
            scope=scope.token,
            title=self._scope_resolver.title(scope),
            status=derive_review_status(
                stored_status_of_set(s.status for s in listing.sources), listing.progress,
            ).value,
            progress=ProgressDTO.of(listing.progress),
            learn_count=sum(self._card_query.learn_counts(ids).values()),
            candidates=listing.cards,
            initially_shown_candidates=(
                None if sort_order == CandidateSortOrder.CHRONOLOGICAL
                else INITIALLY_SHOWN_CANDIDATES
            ),
            busy=any(source_id in listing.operations for source_id in ids),
        )
