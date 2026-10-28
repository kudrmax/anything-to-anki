from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UpdateState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


class UpdateStepStatus(Enum):
    DONE = "done"
    CURRENT = "current"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateStep:
    """One stage of the update as the user sees it, such as "Installing v1.2.0"."""

    title: str
    status: UpdateStepStatus


@dataclass(frozen=True)
class UpdateProgress:
    """How the update started from the app is going. `log_tail` is the end of its log once
    it failed; empty otherwise. `steps` are its stages in order; empty when unknown."""

    state: UpdateState
    log_tail: str = ""
    steps: tuple[UpdateStep, ...] = ()
