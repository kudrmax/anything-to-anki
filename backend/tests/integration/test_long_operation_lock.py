"""The lock a level change holds on every write of the app."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import LongOperationInProgressError
from backend.infrastructure.persistence.database import release_long_operation_lock
from backend.infrastructure.persistence.sqla_long_operation_lock import SqlaLongOperationLock
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_take_then_held(db_session: Session) -> None:
    lock = SqlaLongOperationLock(db_session)
    assert not lock.held()

    lock.take()

    assert lock.held()


def test_take_twice_raises(db_session: Session) -> None:
    lock = SqlaLongOperationLock(db_session)
    lock.take()

    with pytest.raises(LongOperationInProgressError):
        lock.take()


def test_release_absent_is_noop(db_session: Session) -> None:
    lock = SqlaLongOperationLock(db_session)

    lock.release()

    assert not lock.held()


def test_startup_release_clears_row(db_session: Session) -> None:
    SqlaLongOperationLock(db_session).take()
    db_session.commit()

    release_long_operation_lock(sessionmaker(bind=db_session.get_bind()))

    db_session.expire_all()
    assert not SqlaLongOperationLock(db_session).held()
