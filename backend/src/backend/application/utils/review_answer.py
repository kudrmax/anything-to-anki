from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import REVIEW_WINDOW_AROUND
from backend.application.dto.review_dtos import ReviewLayoutDTO, ReviewRowDTO, ReviewUpdateDTO
from backend.domain.value_objects.review_order import CardRow
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.review_header import ReviewHeader
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.value_objects.review_order import LayoutRow, ReviewLayout


def window_around(layout: ReviewLayout, phrase_id: int | None) -> range:
    """The rows on each side of the card's row; the top of the list without the card."""
    index = layout.index_of(phrase_id) if phrase_id is not None else None
    center = index if index is not None else 0
    return rows_from(layout, center - REVIEW_WINDOW_AROUND, 2 * REVIEW_WINDOW_AROUND + 1)


def rows_from(layout: ReviewLayout, start: int, count: int) -> range:
    """`count` rows from `start`, those of them the list has."""
    first = max(start, 0)
    return range(first, max(first, min(start + count, len(layout))))


class ReviewAnswer:
    """The answer of an open review: its header and revision, rows of its visible list and
    the full cards of the card rows sent, which the review then counts as served."""

    def __init__(
        self, header: ReviewHeader, card_states: CardStateQuery, card_views: CardViews,
    ) -> None:
        self._header = header
        self._card_states = card_states
        self._card_views = card_views

    def of(
        self,
        review_id: str,
        review: OpenReview,
        *,
        window: range | None,
        replace: bool,
        focus_id: int | None = None,
    ) -> ReviewUpdateDTO:
        """`window`: the rows to send with their cards. `replace`: the visible list changed;
        the client drops every row it has and gets the rows around the current card instead,
        which are all the review counts as served from then on."""
        layout = review.layout()
        if replace:
            window = window_around(layout, review.current)
            review.served.clear()
        rows = range(0) if window is None else window
        sent = [
            row.phrase_id for row in (layout.row(i) for i in rows) if isinstance(row, CardRow)
        ]
        cards = self._card_views.of_phrases(sent, review.order.sections_of(sent))
        layout_dto = None if window is None else ReviewLayoutDTO(
            version=review.layout_version,
            total_rows=len(layout),
            total_cards=layout.total_cards,
            replace=replace,
            rows=[_row(index, layout.row(index)) for index in rows],
        )
        review.served.update(sent)
        return ReviewUpdateDTO(
            review_id=review_id,
            revision=self._card_states.revision(),
            header=self._header.of(SourceScope.parse(review.scope_token)),
            layout=layout_dto,
            cards=cards,
            focus_id=focus_id,
        )


def _row(index: int, row: LayoutRow) -> ReviewRowDTO:
    if isinstance(row, CardRow):
        return ReviewRowDTO(
            index=index, kind="card", phrase_id=row.phrase_id, position=row.position,
        )
    return ReviewRowDTO(
        index=index, kind="section", section=row.section, count=row.count, open=row.open,
    )
