from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from backend.application.dto.long_operation_dtos import (
    LongOperationOutcome,
    LongOperationStatusDTO,
)
from backend.domain.exceptions import LongOperationCancelledError
from backend.domain.services.long_operation_progress import (
    DONE_PERCENT,
    LongOperationStage,
    percent,
)

if TYPE_CHECKING:
    from backend.domain.value_objects.long_operation_kind import LongOperationKind


class LongOperationProgress:
    """How far the long operation of this process is, and the user's wish to cancel it;
    read by requests while the operation runs on its own thread. One runs at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._operation_id = 0
        self._kind: LongOperationKind | None = None
        self._running = False
        self._stage = LongOperationStage.ANALYSE
        self._part = 0.0
        self._cancel_requested = False
        self._outcome: LongOperationOutcome | None = None
        self._error: str | None = None

    def try_start(self, kind: LongOperationKind) -> bool:
        """False if an operation already runs: it is left as it is."""
        with self._lock:
            if self._running:
                return False
            self._operation_id += 1
            self._kind = kind
            self._running = True
            self._stage = LongOperationStage.ANALYSE
            self._part = 0.0
            self._cancel_requested = False
            self._outcome = None
            self._error = None
            return True

    def abandon(self) -> None:
        """The operation did not start after all: nothing ran, nothing to tell."""
        with self._lock:
            self._running = False

    def step(self, stage: LongOperationStage, part: float) -> None:
        """`part` of the stage is done."""
        with self._lock:
            self._stage, self._part = stage, part

    def check_cancel(self) -> None:
        with self._lock:
            if self._cancel_requested:
                raise LongOperationCancelledError

    def enter_finish(self) -> None:
        """From here the operation can only be committed or fail: a cancel asked for
        before is honoured, one asked for after is refused."""
        with self._lock:
            if self._cancel_requested:
                raise LongOperationCancelledError
            self._stage = LongOperationStage.FINISH

    def cancel(self) -> bool:
        """False if nothing runs or the operation is past cancelling."""
        with self._lock:
            if not self._cancellable():
                return False
            self._cancel_requested = True
            return True

    def succeed(self) -> None:
        self._end(LongOperationOutcome.SUCCEEDED, None)

    def cancelled(self) -> None:
        self._end(LongOperationOutcome.CANCELLED, None)

    def fail(self, error: str) -> None:
        self._end(LongOperationOutcome.FAILED, error)

    def status(self) -> LongOperationStatusDTO:
        with self._lock:
            done = self._outcome is LongOperationOutcome.SUCCEEDED
            return LongOperationStatusDTO(
                operation_id=self._operation_id,
                kind=self._kind,
                running=self._running,
                percent=DONE_PERCENT if done else percent(self._stage, self._part),
                cancellable=self._cancellable(),
                outcome=self._outcome,
                error=self._error,
            )

    def _cancellable(self) -> bool:
        return (
            self._running and not self._cancel_requested
            and self._stage is not LongOperationStage.FINISH
        )

    def _end(self, outcome: LongOperationOutcome, error: str | None) -> None:
        with self._lock:
            self._running = False
            self._outcome = outcome
            self._error = error
