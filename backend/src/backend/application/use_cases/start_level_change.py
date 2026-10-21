from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceOperationBusyError

if TYPE_CHECKING:
    from backend.domain.ports.level_change_lock import LevelChangeLock
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork


class StartLevelChangeUseCase:
    """Takes the level change lock, after which nothing but the change writes. It does not
    start while a source is busy: that operation would be left half way."""

    def __init__(
        self,
        source_lock: SourceOperationLock,
        level_change_lock: LevelChangeLock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._source_lock = source_lock
        self._level_change_lock = level_change_lock
        self._unit_of_work = unit_of_work

    def execute(self) -> None:
        with self._unit_of_work.write():
            busy = self._source_lock.operations()
            if busy:
                source_id, held = next(iter(busy.items()))
                raise SourceOperationBusyError(source_id, held.kind.value)
            self._level_change_lock.take()
