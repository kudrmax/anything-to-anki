from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import Depends

from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator

    from sqlalchemy.orm import Session, sessionmaker

_container: Container | None = None
_session_factory = create_session_factory()


def get_container() -> Container:
    global _container  # noqa: PLW0603
    if _container is None:
        _container = Container()
    return _container


def get_session_factory() -> sessionmaker[Session]:
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def _built[UseCaseT](
    container: Container, build: Callable[[Container, Session], UseCaseT], session: Session,
) -> UseCaseT:
    """What `build` makes of the session, built by the container at hand (which may stand
    in for the real one) rather than by `build`'s own class."""
    built: UseCaseT = getattr(container, build.__name__)(session)
    return built


def use_case[UseCaseT](build: Callable[[Container, Session], UseCaseT]) -> Callable[..., UseCaseT]:
    """A route's dependency on what `build` makes of the request's session. The container
    that serves the request builds it, so a route never holds the session itself."""

    def provide(
        session: Session = Depends(get_db_session),  # noqa: B008
        container: Container = Depends(get_container),  # noqa: B008
    ) -> UseCaseT:
        return _built(container, build, session)

    return provide


class DetachedUseCases:
    """Use cases for work that outlives the request: each on a session of its own, open
    as long as its block."""

    def __init__(self, container: Container, session_factory: sessionmaker[Session]) -> None:
        self._container = container
        self._session_factory = session_factory

    @contextmanager
    def open[UseCaseT](
        self, build: Callable[[Container, Session], UseCaseT],
    ) -> Iterator[UseCaseT]:
        with self._session_factory() as session:
            yield _built(self._container, build, session)


def get_detached_use_cases(
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> DetachedUseCases:
    return DetachedUseCases(container, session_factory)
