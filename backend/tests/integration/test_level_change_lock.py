"""The lock a level change holds on every write of the app."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import LevelChangeInProgressError
from backend.infrastructure.persistence.database import release_level_change_lock
from backend.infrastructure.persistence.sqla_level_change_lock import SqlaLevelChangeLock
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_take_then_held(db_session: Session) -> None:
    lock = SqlaLevelChangeLock(db_session)
    assert not lock.held()

    lock.take()

    assert lock.held()


def test_take_twice_raises(db_session: Session) -> None:
    lock = SqlaLevelChangeLock(db_session)
    lock.take()

    with pytest.raises(LevelChangeInProgressError):
        lock.take()


def test_release_absent_is_noop(db_session: Session) -> None:
    lock = SqlaLevelChangeLock(db_session)

    lock.release()

    assert not lock.held()


def test_startup_release_clears_row(db_session: Session) -> None:
    SqlaLevelChangeLock(db_session).take()
    db_session.commit()

    release_level_change_lock(sessionmaker(bind=db_session.get_bind()))

    db_session.expire_all()
    assert not SqlaLevelChangeLock(db_session).held()
