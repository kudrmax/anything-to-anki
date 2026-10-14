from __future__ import annotations

from enum import StrEnum


class SourceStage(StrEnum):
    """Group of the sources list: what the user does with a source next."""

    IN_PROGRESS = "in_progress"
    PREPARING = "preparing"
    READY = "ready"
    REVIEWED = "reviewed"


STAGE_ORDER: tuple[SourceStage, ...] = (
    SourceStage.IN_PROGRESS,
    SourceStage.PREPARING,
    SourceStage.READY,
    SourceStage.REVIEWED,
)
