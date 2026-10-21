from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.served_text import ServedText
from backend.domain.services.review_layout import layout, unfolded

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    from backend.domain.value_objects.review_order import ReviewLayout, ReviewOrder


class OpenReview:
    """An open review between requests: the sources its set holds, its order from the
    opening, the sections the user opened, the current card, which card rows the client was
    sent, the version of the rows, the version of the set's contents and the chunks of text
    it served. A source is known by its id and the moment it was made: SQLite gives a
    deleted source's id to the next new one. Its visible list is built once per set of
    sections that show."""

    def __init__(
        self,
        *,
        scope_token: str,
        sources: Mapping[int, datetime],
        sort: CandidateSortOrder,
        step: float | None,
        order: ReviewOrder,
        opened: frozenset[CandidateSection],
        current: int | None,
    ) -> None:
        self.scope_token = scope_token
        self.sources = dict(sources)
        self.sort = sort
        self.step = step
        self.order = order
        self.opened = opened
        self.current = current
        self.served: set[int] = set()
        self.layout_version = 0
        # Moves on when the set's sources change: the client reads the contents anew.
        self.contents_version = 0
        self.text = ServedText()
        self._shown: frozenset[CandidateSection] | None = None
        self._layout: ReviewLayout | None = None

    @property
    def source_ids(self) -> frozenset[int]:
        return frozenset(self.sources)

    def reorder(self, order: ReviewOrder) -> None:
        """The order after cards came or went: another list, so the version moves on."""
        self.order = order
        self.layout_version += 1
        self._shown = None
        self._layout = None

    def layout(self) -> ReviewLayout:
        """The visible list as the review stands now; only a list that shows other rows moves
        the version on."""
        shown = unfolded(self.order, self.opened, self.current)
        if self._layout is None or shown != self._shown:
            if self._shown is not None:
                self.layout_version += 1
            self._shown = shown
            self._layout = layout(self.order, self.opened, self.current)
        return self._layout
