from __future__ import annotations

from typing import TYPE_CHECKING

from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

_container: Container | None = None
_session_factory = create_session_factory()


def get_container() -> Container:
    global _container  # noqa: PLW0603
    if _container is None:
        _container = Container()
    return _container


def get_session_factory() -> object:
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
