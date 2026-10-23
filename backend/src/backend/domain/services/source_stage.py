from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import derive_review_status
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.decision_progress import DecisionProgress

_STAGE_BY_STATUS: dict[ReviewStatus, SourceStage] = {
    ReviewStatus.PARTIALLY_REVIEWED: SourceStage.IN_PROGRESS,
    ReviewStatus.DONE: SourceStage.READY,
    ReviewStatus.REVIEWED: SourceStage.REVIEWED,
}
_STARTABLE: Mapping[SourceStatus, bool] = MappingProxyType(
    {SourceStatus.NEW: True, SourceStatus.ERROR: True, SourceStatus.DONE: False},
)


def stage_of(status: ReviewStatus, *, awaiting_generation: bool) -> SourceStage:
    """A topic still waiting for AI is being prepared whatever its status."""
    if awaiting_generation:
        return SourceStage.PREPARING
    return _STAGE_BY_STATUS.get(status, SourceStage.PREPARING)


def source_stage(
    status: SourceStatus, progress: DecisionProgress, *, awaiting_generation: bool,
) -> SourceStage:
    """The stage of a source from its processing status and how far its review got."""
    return stage_of(
        derive_review_status(status, progress), awaiting_generation=awaiting_generation,
    )


def is_pending(
    status: SourceStatus, *, awaiting_generation: bool, busy: bool = False,
) -> bool:
    """Processing can start right now: a topic has to get its targets from AI first, and
    no operation may hold the source."""
    return _STARTABLE[status] and not awaiting_generation and not busy


