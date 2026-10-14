from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

# SQLite takes the write lock at the start of the transaction, not at its first write:
# reads inside it see the state the writes are applied to.
BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"


class SqlaUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork on one SQLite session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    @contextmanager
    def write(self) -> Iterator[None]:
        self._session.commit()
        self._session.connection().exec_driver_sql(BEGIN_IMMEDIATE)
        try:
            yield
        except BaseException:
            self._session.rollback()
            raise
        self._session.commit()
