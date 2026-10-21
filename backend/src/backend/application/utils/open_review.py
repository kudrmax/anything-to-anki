from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.review_layout import layout, unfolded

if TYPE_CHECKING:
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    from backend.domain.value_objects.review_order import ReviewLayout, ReviewOrder


class OpenReview:
    """An open review between requests: its order from the opening, the sections the user
    opened, the current card, which card rows the client was sent and the version of the
    rows. Its visible list is built once per set of sections that show."""

    def __init__(
        self,
        *,
        scope_token: str,
        sort: CandidateSortOrder,
        step: float | None,
        order: ReviewOrder,
        opened: frozenset[CandidateSection],
        current: int | None,
    ) -> None:
        self.scope_token = scope_token
        self.sort = sort
        self.step = step
        self.order = order
        self.opened = opened
        self.current = current
        self.served: set[int] = set()
        self.layout_version = 0
        self._shown: frozenset[CandidateSection] | None = None
        self._layout: ReviewLayout | None = None

    def layout(self) -> ReviewLayout:
        """The visible list as the review stands now; a new one moves the version on."""
        shown = unfolded(self.order, self.opened, self.current) if self.order.sectioned else None
        if self._layout is None or shown != self._shown:
            if self._layout is not None:
                self.layout_version += 1
            self._shown = shown
            self._layout = layout(self.order, self.opened, self.current)
        return self._layout
