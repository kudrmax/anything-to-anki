from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UpdateState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


@dataclass(frozen=True)
class UpdateProgress:
    """How the update started from the app is going. `log_tail` is the end of its log once
    it failed; empty otherwise."""

    state: UpdateState
    log_tail: str = ""
