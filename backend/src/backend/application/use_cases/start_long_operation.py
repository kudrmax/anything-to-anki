from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import LongOperationRunningError, SourceOperationBusyError

if TYPE_CHECKING:
    from backend.domain.ports.long_operation_lock import LongOperationLock
    from backend.domain.ports.running_operations import RunningOperations
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork


class StartLongOperationUseCase:
    """Takes the long operation lock, after which nothing but the operation writes. It does
    not start while a source is busy with a preview or the index is being built: those would
    read what the operation rewrites."""

    def __init__(
        self,
        source_lock: SourceOperationLock,
        long_operation_lock: LongOperationLock,
        unit_of_work: UnitOfWork,
        running: RunningOperations,
    ) -> None:
        self._running = running
        self._source_lock = source_lock
        self._long_operation_lock = long_operation_lock
        self._unit_of_work = unit_of_work

    def execute(self) -> None:
        if self._running.any_running():
            raise LongOperationRunningError
        with self._unit_of_work.write():
            busy = self._source_lock.operations()
            if busy:
                source_id, held = next(iter(busy.items()))
                raise SourceOperationBusyError(source_id, held.kind.value)
            self._long_operation_lock.take()
