from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceOperationBusyError

if TYPE_CHECKING:
    from backend.domain.ports.source_operation_lock import SourceOperationLock


def ensure_source_free(lock: SourceOperationLock, source_id: int) -> None:
    """Generation waits while a long operation (processing, Rebuild) holds the source:
    the phrases it would work on may change or go."""
    held = lock.held(source_id)
    if held is not None:
        raise SourceOperationBusyError(source_id, held)
