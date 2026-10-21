from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class LevelChangeOutcome(Enum):
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LevelChangeStatusDTO(BaseModel):
    """Whether the level is being changed and how far; once it ends, how it ended.
    `change_id` grows with each change started, so a new outcome tells from an old one."""

    change_id: int
    running: bool
    percent: int
    cancellable: bool
    outcome: LevelChangeOutcome | None
    error: str | None
