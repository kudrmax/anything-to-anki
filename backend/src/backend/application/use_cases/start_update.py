from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import LongOperationInProgressError, UpdateAlreadyRunningError
from backend.domain.value_objects.update_progress import UpdateState

if TYPE_CHECKING:
    from backend.domain.ports.long_operation_lock import LongOperationLock
    from backend.domain.ports.update_runner import UpdateRunner


class StartUpdateUseCase:
    """Starts the update of this copy, unless a long operation or an update is running."""

    def __init__(self, lock: LongOperationLock, runner: UpdateRunner) -> None:
        self._lock = lock
        self._runner = runner

    def execute(self) -> None:
        if self._lock.held():
            raise LongOperationInProgressError
        if self._runner.state().state is UpdateState.RUNNING:
            raise UpdateAlreadyRunningError
        self._runner.start()
