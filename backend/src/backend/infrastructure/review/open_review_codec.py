from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.open_review import OpenReview
from backend.domain.value_objects.review_order import ReviewOrder
from backend.infrastructure.review.file_review_order_store import ReviewCodec

if TYPE_CHECKING:
    from datetime import datetime

    from backend.application.utils.served_text import ServedText
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


@dataclass(frozen=True)
class _OpenReviewState:
    scope_token: str
    sources: dict[int, datetime]
    sort: CandidateSortOrder
    step: float | None
    opened: frozenset[CandidateSection]
    current: int | None
    served: frozenset[int]
    layout_version: int
    contents_version: int
    text: ServedText


class OpenReviewCodec(ReviewCodec[OpenReview]):
    """An open review written apart: its order, which only a change of the visible list
    can change, and everything else. The visible list is built anew when read back."""

    def heavy(self, review: OpenReview) -> object:
        return review.order

    def heavy_mark(self, review: OpenReview) -> int:
        return review.layout_version

    def light(self, review: OpenReview) -> object:
        return _OpenReviewState(
            scope_token=review.scope_token,
            sources=review.sources,
            sort=review.sort,
            step=review.step,
            opened=review.opened,
            current=review.current,
            served=frozenset(review.served),
            layout_version=review.layout_version,
            contents_version=review.contents_version,
            text=review.text,
        )

    def joined(self, heavy: object, light: object) -> OpenReview:
        if not isinstance(heavy, ReviewOrder) or not isinstance(light, _OpenReviewState):
            raise TypeError(type(heavy), type(light))
        review = OpenReview(
            scope_token=light.scope_token,
            sources=light.sources,
            sort=light.sort,
            step=light.step,
            order=heavy,
            opened=light.opened,
            current=light.current,
        )
        review.served = set(light.served)
        review.layout_version = light.layout_version
        review.contents_version = light.contents_version
        review.text = light.text
        return review
