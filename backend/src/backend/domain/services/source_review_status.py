from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.value_objects.decision_progress import DecisionProgress

REVIEWABLE_STATUSES = frozenset({
    ReviewStatus.DONE,
    ReviewStatus.PARTIALLY_REVIEWED,
    ReviewStatus.REVIEWED,
})

_OUTSIDE_REVIEW: dict[SourceStatus, ReviewStatus] = {
    SourceStatus.NEW: ReviewStatus.NEW,
    SourceStatus.ERROR: ReviewStatus.ERROR,
}


def derive_review_status(stored: SourceStatus, progress: DecisionProgress) -> ReviewStatus:
    """What a source reads as now: a processed source is reviewed when every card that
    counts is done, not started while none is, partially reviewed in between."""
    if stored is not SourceStatus.DONE:
        return _OUTSIDE_REVIEW[stored]
    if progress.decided == progress.total:
        return ReviewStatus.REVIEWED
    if progress.decided == 0:
        return ReviewStatus.DONE
    return ReviewStatus.PARTIALLY_REVIEWED
