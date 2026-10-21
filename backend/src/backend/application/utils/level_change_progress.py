from __future__ import annotations

import threading

from backend.application.dto.level_change_dtos import LevelChangeOutcome, LevelChangeStatusDTO
from backend.domain.exceptions import LevelChangeCancelledError
from backend.domain.services.level_change_progress import (
    DONE_PERCENT,
    LevelChangeStage,
    percent,
)


class LevelChangeProgress:
    """How far the level change of this process is, and the user's wish to cancel it; read
    by requests while the change runs on its own thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._stage = LevelChangeStage.ANALYSE
        self._done = 0
        self._total = 0
        self._cancel_requested = False
        self._outcome: LevelChangeOutcome | None = None
        self._error: str | None = None

    def try_start(self) -> bool:
        """False if a change already runs: it is left as it is."""
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stage = LevelChangeStage.ANALYSE
            self._done = self._total = 0
            self._cancel_requested = False
            self._outcome = None
            self._error = None
            return True

    def abandon(self) -> None:
        """The change did not start after all: nothing ran, nothing to tell."""
        with self._lock:
            self._running = False

    def step(self, stage: LevelChangeStage, done: int, total: int) -> None:
        with self._lock:
            self._stage, self._done, self._total = stage, done, total

    def check_cancel(self) -> None:
        with self._lock:
            if self._cancel_requested:
                raise LevelChangeCancelledError

    def enter_finish(self) -> None:
        """From here the change can only be committed or fail: a cancel asked for before
        is honoured, one asked for after is refused."""
        with self._lock:
            if self._cancel_requested:
                raise LevelChangeCancelledError
            self._stage = LevelChangeStage.FINISH

    def cancel(self) -> bool:
        """False if nothing runs or the change is past cancelling."""
        with self._lock:
            if not self._cancellable():
                return False
            self._cancel_requested = True
            return True

    def succeed(self) -> None:
        self._end(LevelChangeOutcome.SUCCEEDED, None)

    def cancelled(self) -> None:
        self._end(LevelChangeOutcome.CANCELLED, None)

    def fail(self, error: str) -> None:
        self._end(LevelChangeOutcome.FAILED, error)

    def status(self) -> LevelChangeStatusDTO:
        with self._lock:
            done = self._outcome is LevelChangeOutcome.SUCCEEDED
            return LevelChangeStatusDTO(
                running=self._running,
                percent=DONE_PERCENT if done else percent(self._stage, self._done, self._total),
                cancellable=self._cancellable(),
                outcome=self._outcome,
                error=self._error,
            )

    def _cancellable(self) -> bool:
        return (
            self._running and not self._cancel_requested
            and self._stage is not LevelChangeStage.FINISH
        )

    def _end(self, outcome: LevelChangeOutcome, error: str | None) -> None:
        with self._lock:
            self._running = False
            self._outcome = outcome
            self._error = error
