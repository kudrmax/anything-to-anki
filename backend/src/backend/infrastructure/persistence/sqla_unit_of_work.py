from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from backend.domain.exceptions import NestedWriteError, UncommittedWorkError, WriteInReadError
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.write_gate import RefuseDuringLongOperation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sqlalchemy.orm import Session

    from backend.application.utils.knowledge_scope import KnowledgeScope
    from backend.domain.value_objects.card_change import CardChange
    from backend.infrastructure.persistence.write_gate import WriteGate

# SQLite takes the write lock at the start of the transaction, not at its first write:
# reads inside it see the state the writes are applied to.
BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"
# A read transaction takes its snapshot at its first read and never the write lock.
BEGIN_DEFERRED = "BEGIN DEFERRED"
# Kept on the session, not the unit of work: every unit of work on a session sees it.
WRITE_OPEN_KEY = "unit_of_work.write_open"
READ_OPEN_KEY = "unit_of_work.read_open"
# SQLite refuses every write of a connection in query-only mode, flushed or not, with this.
_QUERY_ONLY_REFUSAL = "attempt to write a readonly database"
COMMIT_CHECKS_KEY = "unit_of_work.commit_checks"


def add_commit_check(session: Session, check: Callable[[], None]) -> None:
    """Every write on the session runs `check` last, inside its transaction; a check that
    raises rolls the write back."""
    session.info.setdefault(COMMIT_CHECKS_KEY, []).append(check)


class SqlaUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork on one SQLite session; `knowledge` is the
    session's scope, read again inside each write transaction. A write open through any
    unit of work on the session makes another one there a nested write. The session's
    commit checks run before each commit. The changes the session's recorder holds are
    drained by every write: passed to `before_commit` right before the commit, or dropped
    when there is none or the write fails. While a level change holds its lock, `gate`
    decides whether a write is refused (the default), waits, or goes on."""

    def __init__(
        self,
        session: Session,
        knowledge: KnowledgeScope,
        before_commit: Callable[[tuple[CardChange, ...]], None] | None = None,
        gate: WriteGate | None = None,
    ) -> None:
        self._session = session
        self._gate = gate if gate is not None else RefuseDuringLongOperation()
        self._knowledge = knowledge
        self._recorder = SessionChangeRecorder(session)
        self._before_commit = before_commit

    @contextmanager
    def write(self) -> Iterator[None]:
        if self._session.info.get(READ_OPEN_KEY, False):
            raise WriteInReadError
        if self._session.info.get(WRITE_OPEN_KEY, False):
            raise NestedWriteError
        if self._has_pending_work():
            raise UncommittedWorkError
        # Ends the read transaction: BEGIN IMMEDIATE cannot start inside it.
        self._session.commit()
        self._begin_through_gate()
        self._session.info[WRITE_OPEN_KEY] = True
        try:
            self._knowledge.invalidate()
            yield
            for check in self._session.info.get(COMMIT_CHECKS_KEY, ()):
                check()
            changes = self._recorder.drain()
            if self._before_commit is not None:
                self._before_commit(changes)
            self._session.commit()
        except BaseException:
            self._recorder.drain()
            self._session.rollback()
            raise
        finally:
            self._session.info[WRITE_OPEN_KEY] = False

    def _begin_through_gate(self) -> None:
        """The lock is looked at before BEGIN IMMEDIATE too: the level change holds the
        database for its one write longer than SQLite's busy timeout, and a write that
        waited for it there would fail instead of meeting the gate. The look inside the
        transaction is the one that counts; the change takes its lock minutes before its
        write, so a write that saw no lock is long done by then."""
        while True:
            try:
                admitted = self._gate.admit(self._session)
            finally:
                self._session.rollback()
            if not admitted:
                self._gate.wait()
                continue
            self._session.connection().exec_driver_sql(BEGIN_IMMEDIATE)
            try:
                admitted = self._gate.admit(self._session)
            except BaseException:
                self._session.rollback()
                raise
            if admitted:
                return
            self._session.rollback()
            self._gate.wait()

    @contextmanager
    def read(self) -> Iterator[None]:
        session = self._session
        if session.new or session.dirty or session.deleted:
            raise UncommittedWorkError
        dbapi_connection = session.connection().connection.dbapi_connection
        if session.info.get(WRITE_OPEN_KEY, False) or (
            dbapi_connection is not None and dbapi_connection.in_transaction
        ):
            yield
            return
        # The connection is the one the transaction runs on: the session gives it back to
        # the pool at the rollback, so query-only is turned off on it before.
        connection = session.connection()
        connection.exec_driver_sql(BEGIN_DEFERRED)
        connection.exec_driver_sql("PRAGMA query_only = ON")
        session.info[READ_OPEN_KEY] = True
        event.listen(session, "before_flush", _refuse_flush)
        try:
            yield
        except OperationalError as e:
            if _QUERY_ONLY_REFUSAL in str(e):
                raise WriteInReadError from e
            raise
        finally:
            event.remove(session, "before_flush", _refuse_flush)
            session.info[READ_OPEN_KEY] = False
            connection.exec_driver_sql("PRAGMA query_only = OFF")
            session.rollback()

    def _has_pending_work(self) -> bool:
        """Changes not flushed yet, or already sent to SQLite: pysqlite opens a transaction
        on the connection only for a write, so an open one there holds written rows."""
        session = self._session
        if session.new or session.dirty or session.deleted:
            return True
        dbapi_connection = session.connection().connection.dbapi_connection
        return dbapi_connection is not None and bool(dbapi_connection.in_transaction)


def _refuse_flush(*_args: object) -> None:
    """A read transaction flushes nothing: the session's changes would be written in it."""
    raise WriteInReadError
