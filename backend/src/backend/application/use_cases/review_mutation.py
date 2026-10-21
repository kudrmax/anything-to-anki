from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.review_updates import Placement
from backend.domain.services.review_layout import focus_after_press

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from backend.application.dto.review_dtos import ReviewContext, ReviewUpdateDTO
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.review_updates import ReviewUpdates
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.review_order_store import ReviewOrderStore
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.review_order import ReviewOrder


class ReviewMutation:
    """A change made on an open review: the action runs, which writes in its own
    transaction, and the answer is what changed since the client's revision with the card
    the focus goes to. ReviewNotFoundError, before the action runs, when the review is not
    held any more; an error of the action goes out as it is.

    A press, a replacement and an added word run under the review's lock, so the focus
    reads the review as their own write left it; any other change runs without it, and the
    review stays held until it answers."""

    def __init__(
        self,
        store: ReviewOrderStore[OpenReview],
        updates: ReviewUpdates,
        card_states: CardStateQuery,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._store = store
        self._updates = updates
        self._card_states = card_states
        self._unit_of_work = unit_of_work

    def press(
        self, ctx: ReviewContext, phrase_id: int, action: Callable[[], object],
    ) -> ReviewUpdateDTO:
        """A button of the card pressed: the focus moves on when the card became done."""
        with self._store.hold(ctx.review_id) as review:
            with self._unit_of_work.read():
                was_done = self._card_states.done_of_phrases([phrase_id]).get(phrase_id, False)
            action()

            def focus(order: ReviewOrder, is_done: Mapping[int, bool]) -> int | None:
                return focus_after_press(order, phrase_id, was_done, is_done)

            return self._updates.build(ctx, review, focus_by=focus)

    def replace(
        self, ctx: ReviewContext, old_id: int, action: Callable[[], CardDTO],
    ) -> ReviewUpdateDTO:
        """The card replaced by the one `action` makes: it takes the old card's place and
        the focus."""
        with self._store.hold(ctx.review_id) as review:
            card = action()
            return self._updates.build(
                ctx, review, focus_id=card.phrase_id,
                placement=Placement(old_id=old_id, new_id=card.phrase_id),
            )

    def add(self, ctx: ReviewContext, action: Callable[[], CardDTO]) -> ReviewUpdateDTO:
        """A word added: its card joins the order and takes the focus."""
        with self._store.hold(ctx.review_id) as review:
            card = action()
            return self._updates.build(ctx, review, focus_id=card.phrase_id)

    def edit[T](
        self, ctx: ReviewContext, action: Callable[[], T],
    ) -> tuple[T, ReviewUpdateDTO]:
        """Any other change: what the action gives, and what changed. The focus stays."""
        with self._store.pin(ctx.review_id):
            result = action()
            with self._store.hold(ctx.review_id) as review:
                return result, self._updates.build(ctx, review)
