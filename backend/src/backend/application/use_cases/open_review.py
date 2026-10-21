from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.open_review import OpenReview
from backend.application.utils.review_answer import window_around
from backend.domain.services.candidate_sorting import sort_cards, stored_standing
from backend.domain.services.review_layout import initial_focus
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.review_order import HeldCard, ReviewOrder
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.dto.review_dtos import OpenReviewRequest, ReviewUpdateDTO
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.review_answer import ReviewAnswer
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.review_order_store import ReviewOrderStore
    from backend.domain.ports.unit_of_work import UnitOfWork


class OpenReviewUseCase:
    """Opens the review of a set of sources: its order is computed once, from the stored card
    states, and held under a new review id. The answer lands on the card asked for, else the
    first one not done, with the rows around it."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        card_states: CardStateQuery,
        threshold_resolver: FrequentWordThresholdResolver,
        candidate_sorter: CandidateSorter,
        store: ReviewOrderStore[OpenReview],
        answer: ReviewAnswer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._card_states = card_states
        self._threshold_resolver = threshold_resolver
        self._candidate_sorter = candidate_sorter
        self._store = store
        self._answer = answer
        self._unit_of_work = unit_of_work

    def execute(self, request: OpenReviewRequest) -> ReviewUpdateDTO:
        """ValueError for a scope token that names no set."""
        scope = SourceScope.parse(request.scope)
        with self._unit_of_work.read():
            sources = self._scope_resolver.reviewable_sources(scope)
            source_ids = [s.id for s in sources if s.id is not None]
            rows = self._card_states.order_rows(source_ids)
            step = self._threshold_resolver.resolve().zipf
            ordered = sort_cards(
                rows, request.sort, stored_standing(step),
                usage_order=self._candidate_sorter.usage_order(), source_order=source_ids,
            )
            order = ReviewOrder(
                (HeldCard(c.phrase_id, c.word_id, c.sections.at(step)) for c in ordered),
                sectioned=request.sort != CandidateSortOrder.CHRONOLOGICAL,
            )
            focus = initial_focus(
                order, {c.phrase_id: c.is_done for c in rows}, request.requested_id,
            )
            review = OpenReview(
                scope_token=scope.token,
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
