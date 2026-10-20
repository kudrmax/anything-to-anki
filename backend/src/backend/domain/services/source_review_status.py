from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.card_view import reach
from backend.domain.value_objects.decision_progress import ReviewReach
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from backend.domain.value_objects.decision_progress import DecisionProgress

# Every review status, said once each: a new status has to be placed in both tables.
REVIEWABLE: Mapping[ReviewStatus, bool] = MappingProxyType({
    ReviewStatus.NEW: False,
    ReviewStatus.ERROR: False,
    ReviewStatus.DONE: True,
    ReviewStatus.PARTIALLY_REVIEWED: True,
    ReviewStatus.REVIEWED: True,
})
IS_REVIEWED: Mapping[ReviewStatus, bool] = MappingProxyType({
    ReviewStatus.NEW: False,
    ReviewStatus.ERROR: False,
    ReviewStatus.DONE: False,
    ReviewStatus.PARTIALLY_REVIEWED: False,
    ReviewStatus.REVIEWED: True,
})

_REVIEW_STATUS: Mapping[tuple[SourceStatus, ReviewReach], ReviewStatus] = MappingProxyType({
    **{(SourceStatus.NEW, reached): ReviewStatus.NEW for reached in ReviewReach},
    **{(SourceStatus.ERROR, reached): ReviewStatus.ERROR for reached in ReviewReach},
    (SourceStatus.DONE, ReviewReach.NONE): ReviewStatus.DONE,
    (SourceStatus.DONE, ReviewReach.SOME): ReviewStatus.PARTIALLY_REVIEWED,
    (SourceStatus.DONE, ReviewReach.ALL): ReviewStatus.REVIEWED,
})


def derive_review_status(stored: SourceStatus, progress: DecisionProgress) -> ReviewStatus:
    """What a source reads as now: a processed source is reviewed when every card that
    counts is done, not started while none is, partially reviewed in between."""
    return _REVIEW_STATUS[(stored, reach(progress))]


def stored_status_of_set(statuses: Iterable[SourceStatus]) -> SourceStatus:
    """A set is processed once any of its sources is, failed when every source failed,
    new otherwise; an empty set is new."""
    seen = list(statuses)
    if SourceStatus.DONE in seen:
        return SourceStatus.DONE
    if seen and all(stored is SourceStatus.ERROR for stored in seen):
        return SourceStatus.ERROR
    return SourceStatus.NEW
