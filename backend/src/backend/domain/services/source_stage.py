from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

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


PROCESSING = "processing"


def is_pending(
    status: SourceStatus, *, awaiting_generation: bool, busy: bool = False,
) -> bool:
    """Processing can start right now: a topic has to get its targets from AI first, and
    no operation may hold the source."""
    return _STARTABLE[status] and not awaiting_generation and not busy


def shown_status(status: ReviewStatus, busy_with: SourceOperationKind | None) -> str:
    """The status a source shows: 'processing' while it is processed, else its outcome."""
    return PROCESSING if busy_with is SourceOperationKind.PROCESS else status.value
