from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import REVIEW_ROWS_MAX
from backend.application.utils.review_answer import rows_from, window_around
from backend.domain.exceptions import PhraseNotFoundError

if TYPE_CHECKING:
    from backend.application.dto.document_dtos import ReviewContentsDTO
    from backend.application.dto.review_dtos import ReviewContext, ReviewUpdateDTO
    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.review_answer import ReviewAnswer
    from backend.application.utils.review_text import ReviewText
    from backend.application.utils.review_updates import ReviewUpdates
    from backend.domain.ports.review_order_store import ReviewOrderStore
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.candidate_section import CandidateSection


class ReviewWindowUseCase:
    """Reads of an open review: rows of its visible list, the rows around a card, a section
    opened or folded, what changed, the contents of its set and a chunk of a source's text.
    Each but the contents first records the card the client shows: its
    section opens by itself. When that or the request changes the visible list, the answer
    sends every row served before, indexed anew. ReviewNotFoundError when the review is not
    held any more."""

    def __init__(
        self,
        store: ReviewOrderStore[OpenReview],
        answer: ReviewAnswer,
        updates: ReviewUpdates,
        text: ReviewText,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._store = store
        self._answer = answer
        self._updates = updates
        self._text = text
        self._unit_of_work = unit_of_work

    def rows(self, ctx: ReviewContext, start: int, count: int) -> ReviewUpdateDTO:
        """`count` rows from `start`, at most REVIEW_ROWS_MAX."""
        with self._store.hold(ctx.review_id) as review, self._unit_of_work.read():
            replace = _moved(review, ctx.current)
            window = rows_from(review.layout(), start, min(count, REVIEW_ROWS_MAX))
            return self._answer.of(ctx.review_id, review, window=window, replace=replace)

    def around(self, ctx: ReviewContext, phrase_id: int) -> ReviewUpdateDTO:
        """The rows around the card, which becomes the current one. PhraseNotFoundError when
        the review does not hold it."""
        with self._store.hold(ctx.review_id) as review, self._unit_of_work.read():
            if review.order.card(phrase_id) is None:
                raise PhraseNotFoundError(phrase_id)
            replace = _moved(review, phrase_id)
            return self._answer.of(
                ctx.review_id, review,
                window=window_around(review.layout(), phrase_id), replace=replace,
                focus_id=phrase_id,
            )

    def set_section(
        self, ctx: ReviewContext, section: CandidateSection, *, is_open: bool,
    ) -> ReviewUpdateDTO:
        """The section opened or folded; the current card's stays open while it holds it."""
        with self._store.hold(ctx.review_id) as review, self._unit_of_work.read():
            version = review.layout_version
            review.current = ctx.current
            review.opened = (
                review.opened | {section} if is_open else review.opened - {section}
            )
            review.layout()
            replace = review.layout_version != version
            return self._answer.of(
                ctx.review_id, review, window=None if replace else range(0), replace=replace,
            )

    def contents(self, ctx: ReviewContext) -> ReviewContentsDTO:
        """The sources of the set that have a document, in the set's order."""
        with self._store.hold(ctx.review_id) as review, self._unit_of_work.read():
            return self._text.contents(review)

    def text(
        self, ctx: ReviewContext, source_id: int, block: int | None, at: int | None = None,
    ) -> ReviewUpdateDTO:
        """The chunk of the source's text that holds the block (LAST_BLOCK: the last one)
        or, with no block, the character at offset `at`, with no rows unless the current
        card changed the visible list."""
        with self._store.hold(ctx.review_id) as review, self._unit_of_work.read():
            chunk = self._text.chunk(review, source_id, block, at)
            replace = _moved(review, ctx.current)
            return self._answer.of(
                ctx.review_id, review, window=None, replace=replace, text=chunk,
            )

    def changes(self, ctx: ReviewContext) -> ReviewUpdateDTO:
        """What changed since the client's revision, placed into the held order."""
        with self._store.hold(ctx.review_id) as review:
            return self._updates.build(ctx, review)


def _moved(review: OpenReview, current: int | None) -> bool:
    """Records the current card; whether that changed the visible list."""
    version = review.layout_version
    review.current = current
    review.layout()
    return review.layout_version != version
