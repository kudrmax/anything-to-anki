from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.open_review import OpenReview
from backend.application.utils.review_answer import window_around
from backend.domain.services.review_layout import initial_focus
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.review_order import ReviewOrder
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.dto.review_dtos import OpenReviewRequest, ReviewUpdateDTO
    from backend.application.utils.review_answer import ReviewAnswer
    from backend.application.utils.review_ordering import ReviewOrdering
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.review_order_store import ReviewOrderStore
    from backend.domain.ports.unit_of_work import UnitOfWork


class OpenReviewUseCase:
    """Opens the review of a set of sources: its order is computed once, from the stored card
    states, and held under a new review id. The answer lands on the card asked for, else the
    first one not done, with the rows around it."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        ordering: ReviewOrdering,
        store: ReviewOrderStore[OpenReview],
        answer: ReviewAnswer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._ordering = ordering
        self._store = store
        self._answer = answer
        self._unit_of_work = unit_of_work

    def execute(self, request: OpenReviewRequest) -> ReviewUpdateDTO:
        """ValueError for a scope token that names no set."""
        scope = SourceScope.parse(request.scope)
        with self._unit_of_work.read():
            sources = self._scope_resolver.reviewable_sources(scope)
            source_ids = [s.id for s in sources if s.id is not None]
            step = self._ordering.step()
            pairs = self._ordering.ordered(source_ids, request.sort, step)
            ordered = [card for card, _ in pairs]
            order = ReviewOrder(
                self._ordering.held(ordered, step, {c.phrase_id: k for c, k in pairs}),
                sectioned=request.sort != CandidateSortOrder.CHRONOLOGICAL,
            )
            focus = initial_focus(
                order, {c.phrase_id: c.is_done for c in ordered}, request.requested_id,
            )
            review = OpenReview(
                scope_token=scope.token,
                source_ids=frozenset(source_ids),
                sort=request.sort,
                step=step,
                order=order,
                opened=frozenset(request.open_sections),
                current=focus,
            )
            # Answered from the review itself, not held back from the store: the store may
            # let it go before the answer, and no other request knows its id yet.
            review_id = self._store.open(review)
            return self._answer.of(
                review_id, review,
                window=window_around(review.layout(), focus), replace=True, focus_id=focus,
            )
