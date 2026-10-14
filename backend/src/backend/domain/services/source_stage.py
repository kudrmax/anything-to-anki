from __future__ import annotations

from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus

_STAGE_BY_STATUS: dict[SourceStatus, SourceStage] = {
    SourceStatus.PARTIALLY_REVIEWED: SourceStage.IN_PROGRESS,
    SourceStatus.DONE: SourceStage.READY,
    SourceStatus.REVIEWED: SourceStage.REVIEWED,
}
_STARTABLE = frozenset({SourceStatus.NEW, SourceStatus.ERROR})


def stage_of(status: SourceStatus, *, awaiting_generation: bool) -> SourceStage:
    """A topic still waiting for AI is being prepared whatever its status."""
    if awaiting_generation:
        return SourceStage.PREPARING
    return _STAGE_BY_STATUS.get(status, SourceStage.PREPARING)


def is_pending(status: SourceStatus, *, awaiting_generation: bool) -> bool:
    """Processing can start right now: a topic has to get its targets from AI first."""
    return status in _STARTABLE and not awaiting_generation
