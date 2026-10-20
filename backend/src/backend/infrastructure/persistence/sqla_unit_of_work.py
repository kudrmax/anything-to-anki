from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import NestedWriteError
from backend.domain.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sqlalchemy.orm import Session

    from backend.application.utils.knowledge_scope import KnowledgeScope

# SQLite takes the write lock at the start of the transaction, not at its first write:
# reads inside it see the state the writes are applied to.
BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"
# Kept on the session, not the unit of work: every unit of work on a session sees it.
WRITE_OPEN_KEY = "unit_of_work.write_open"
COMMIT_CHECKS_KEY = "unit_of_work.commit_checks"


def add_commit_check(session: Session, check: Callable[[], None]) -> None:
    """Every write on the session runs `check` last, inside its transaction; a check that
    raises rolls the write back."""
    session.info.setdefault(COMMIT_CHECKS_KEY, []).append(check)


class SqlaUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork on one SQLite session; `knowledge` is the
    session's scope, read again inside each write transaction. A write open through any
    unit of work on the session makes another one there a nested write. The session's
    commit checks run before each commit."""

    def __init__(self, session: Session, knowledge: KnowledgeScope) -> None:
        self._session = session
        self._knowledge = knowledge

    @contextmanager
    def write(self) -> Iterator[None]:
        if self._session.info.get(WRITE_OPEN_KEY, False):
            raise NestedWriteError
        self._session.commit()
        self._session.connection().exec_driver_sql(BEGIN_IMMEDIATE)
        self._session.info[WRITE_OPEN_KEY] = True
        try:
            self._knowledge.invalidate()
            yield
            for check in self._session.info.get(COMMIT_CHECKS_KEY, ()):
                check()
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise
        finally:
            self._session.info[WRITE_OPEN_KEY] = False
