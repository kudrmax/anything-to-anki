from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.card_view import reach
from backend.domain.value_objects.decision_progress import ReviewReach
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.decision_progress import DecisionProgress

REVIEWABLE_STATUSES = frozenset({
    ReviewStatus.DONE,
    ReviewStatus.PARTIALLY_REVIEWED,
    ReviewStatus.REVIEWED,
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
