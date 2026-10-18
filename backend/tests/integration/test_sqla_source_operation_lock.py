"""The lock a long operation takes on its source."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)

from tests.integration.conftest import insert_source

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE = 1
OTHER_SOURCE = 2


def test_a_source_is_held_by_one_operation_at_a_time(db_session: Session) -> None:
    insert_source(db_session, SOURCE)
    insert_source(db_session, OTHER_SOURCE)
    lock = SqlaSourceOperationLock(db_session)

    assert lock.acquire(SOURCE, SourceOperationKind.REBUILD)
    assert not lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    assert lock.acquire(OTHER_SOURCE, SourceOperationKind.PROCESS)
    assert lock.held(SOURCE) is SourceOperationKind.REBUILD

    lock.release(SOURCE)
    assert lock.held(SOURCE) is None
    assert lock.acquire(SOURCE, SourceOperationKind.PROCESS)

    lock.clear_all()
    assert (lock.held(SOURCE), lock.held(OTHER_SOURCE)) == (None, None)
