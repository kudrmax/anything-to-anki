from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

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


def use_case[UseCaseT](build: Callable[[Container, Session], UseCaseT]) -> Callable[..., UseCaseT]:
    """A route's dependency on what `build` makes of the request's session. The container
    that serves the request builds it, so a route never holds the session itself."""
    name = build.__name__

    def provide(
        session: Session = Depends(get_db_session),  # noqa: B008
        container: Container = Depends(get_container),  # noqa: B008
    ) -> UseCaseT:
        built: UseCaseT = getattr(container, name)(session)
        return built

    return provide
