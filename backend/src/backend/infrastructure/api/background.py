from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from backend.infrastructure.api.source_operations import SourceOperationRegistry

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[None]] = set()


def in_background(work: Coroutine[object, object, None]) -> None:
    """Runs the work after the response; the task is kept until it is done."""
    task = asyncio.create_task(work)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def operation_background(
    operations: SourceOperationRegistry,
    scope: str,
    operation_id: int,
    run: Callable[[], None],
) -> None:
    """`run` does the operation on a session of its own; each source of the set is taken
    and freed by the run itself. A failure ends the operation in error."""
    try:
        await asyncio.to_thread(run)
    except Exception as e:
        logger.exception("Background operation failed (scope=%s)", scope)
        operations.failed(scope, operation_id, str(e))
