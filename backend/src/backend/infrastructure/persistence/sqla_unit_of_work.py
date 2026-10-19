from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from backend.application.utils.knowledge_scope import KnowledgeScope

# SQLite takes the write lock at the start of the transaction, not at its first write:
# reads inside it see the state the writes are applied to.
BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"


class SqlaUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork on one SQLite session; `knowledge` is the
    session's scope, read again inside each write transaction."""

    def __init__(self, session: Session, knowledge: KnowledgeScope) -> None:
        self._session = session
        self._knowledge = knowledge

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    @contextmanager
    def write(self) -> Iterator[None]:
        self._session.commit()
        self._session.connection().exec_driver_sql(BEGIN_IMMEDIATE)
        self._knowledge.invalidate()
        try:
            yield
        except BaseException:
            self._session.rollback()
            raise
        self._session.commit()
