"""Notes exported to Anki, and the lock a long operation takes on its source."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.sqla_anki_note_repository import SqlaAnkiNoteRepository
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)

from tests.integration.conftest import insert_source

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

AT = datetime(2026, 10, 15, tzinfo=UTC)
SOURCE = 1
OTHER_SOURCE = 2


def test_notes_wait_until_matured_or_deleted(db_session: Session) -> None:
    notes = SqlaAnkiNoteRepository(db_session)
    notes.add(1, "glare", "VERB")
    notes.add(2, "linger", None)
    notes.add(3, "wander", "VERB")

    notes.mark_matured([1], AT)
    notes.mark_deleted([2], AT)

    assert [n.note_id for n in notes.pending()] == [3]


def test_adding_a_note_again_keeps_it_as_it_was(db_session: Session) -> None:
    notes = SqlaAnkiNoteRepository(db_session)
    notes.add(1, "glare", "VERB")
    notes.mark_matured([1], AT)

    notes.add(1, "other", None)

    assert notes.pending() == []
    assert notes.has_lemma("Glare")
    assert not notes.has_lemma("other")


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
