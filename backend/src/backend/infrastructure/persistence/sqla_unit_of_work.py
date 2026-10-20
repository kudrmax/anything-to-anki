from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import NestedWriteError
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
        self._write_open = False

    @contextmanager
    def write(self) -> Iterator[None]:
        if self._write_open:
            raise NestedWriteError
        self._session.commit()
        self._session.connection().exec_driver_sql(BEGIN_IMMEDIATE)
        self._write_open = True
        try:
            self._knowledge.invalidate()
            yield
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        finally:
            self._write_open = False
