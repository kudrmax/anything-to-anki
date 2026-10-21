from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.sqla_unit_of_work import add_commit_check

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sqlalchemy.orm import Session, sessionmaker

    from backend.domain.ports.unit_of_work import UnitOfWork

type SessionBuild[T] = Callable[[Session], T]


class SessionWork:
    """Work outside a request (the worker, background passes), each piece on a session of
    its own from the one factory. It writes only through the unit of work of its session."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        unit_of_work: SessionBuild[UnitOfWork],
    ) -> None:
        self._session_factory = session_factory
        self._unit_of_work = unit_of_work

    @contextmanager
    def open[T](
        self, build: SessionBuild[T], commit_check: SessionBuild[None] | None = None,
    ) -> Iterator[T]:
        """What `build` makes of a new session, open as long as the block. Every write on
        that session runs `commit_check` on it before committing."""
        with self._session_factory() as session:
            if commit_check is not None:
                add_commit_check(session, lambda: commit_check(session))
            yield build(session)

    def write[T](self, change: SessionBuild[T]) -> T:
        """`change` in one write transaction on a new session."""
        with self._session_factory() as session, self._unit_of_work(session).write():
            return change(session)

    def read[T](self, query: SessionBuild[T]) -> T:
        with self._session_factory() as session:
            return query(session)
