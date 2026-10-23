from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CursorResult, delete, exists, insert, select

from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.ports.long_operation_lock import LongOperationLock
from backend.infrastructure.persistence.models import LongOperationLockModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

LOCK_ROW_ID = 1


class SqlaLongOperationLock(LongOperationLock):
    """SQLAlchemy implementation of LongOperationLock: one row, there or not, seen by every
    process on the database."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def take(self) -> None:
        result: CursorResult[tuple[()]] = self._session.execute(  # type: ignore[assignment]
            insert(LongOperationLockModel)
            .prefix_with("OR IGNORE")
            .values(id=LOCK_ROW_ID, started_at=datetime.now(tz=UTC))
        )
        self._session.flush()
        if result.rowcount != 1:
            raise LongOperationInProgressError

    def held(self) -> bool:
        return bool(self._session.scalar(select(exists().select_from(LongOperationLockModel))))

    def release(self) -> None:
        self._session.execute(delete(LongOperationLockModel))
        self._session.flush()
