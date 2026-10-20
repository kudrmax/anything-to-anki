from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from sqlalchemy.orm import Session, sessionmaker

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
    session_factory: sessionmaker[Session],
    prepare: Callable[[Session], Callable[[], None]],
) -> None:
    """`prepare` builds the run in a background session of its own; each source of the
    set is taken and freed by the run itself. A failure ends the operation in error."""
    bg_session: Session | None = None
    try:
        bg_session = session_factory()
        run = prepare(bg_session)
        await asyncio.to_thread(run)
    except Exception as e:
        logger.exception("Background operation failed (scope=%s)", scope)
        operations.failed(scope, operation_id, str(e))
    finally:
        if bg_session is not None:
            bg_session.close()


def free_source(source_id: int, session_factory: sessionmaker[Session]) -> None:
    """Release a source whose operation never started running."""
    try:
        session: Session = session_factory()
    except Exception:
        logger.exception("Failed to free source %d", source_id)
        return
    try:
        SqlaSourceOperationLock(session).release(source_id)
        session.commit()
    except Exception:
        logger.exception("Failed to free source %d", source_id)
        session.rollback()
    finally:
        session.close()
