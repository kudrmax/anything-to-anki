from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import backend.infrastructure.persistence.models  # noqa: F401  registers every table on Base
import pytest
from backend.domain.value_objects.card_change import (
    CardChange,
    DecisionChanged,
    LevelChanged,
    PhraseChanged,
)
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'recorder.db'}")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


class _Seen:
    def __init__(self) -> None:
        self.calls: list[tuple[CardChange, ...]] = []

    def __call__(self, changes: tuple[CardChange, ...]) -> None:
        self.calls.append(changes)


def test_recorders_on_one_session_share_events(session: Session) -> None:
    SessionChangeRecorder(session).record(PhraseChanged(1))

    assert SessionChangeRecorder(session).drain() == (PhraseChanged(1),)


def test_drain_keeps_order_drops_exact_duplicates_and_empties(session: Session) -> None:
    recorder = SessionChangeRecorder(session)
    for change in (PhraseChanged(2), DecisionChanged("run"), PhraseChanged(2), LevelChanged()):
        recorder.record(change)

    assert recorder.drain() == (PhraseChanged(2), DecisionChanged("run"), LevelChanged())
    assert recorder.drain() == ()


def test_committed_write_hands_its_events_to_before_commit_once(session: Session) -> None:
    seen = _Seen()
    unit_of_work = SqlaUnitOfWork(session, MagicMock(), before_commit=seen)

    with unit_of_work.write():
        SessionChangeRecorder(session).record(PhraseChanged(1))

    assert seen.calls == [(PhraseChanged(1),)]
    assert SessionChangeRecorder(session).drain() == ()


def test_failed_write_never_reaches_before_commit_and_leaves_nothing(session: Session) -> None:
    seen = _Seen()
    unit_of_work = SqlaUnitOfWork(session, MagicMock(), before_commit=seen)

    with pytest.raises(RuntimeError), unit_of_work.write():
        SessionChangeRecorder(session).record(PhraseChanged(1))
        raise RuntimeError

    assert seen.calls == []
    assert SessionChangeRecorder(session).drain() == ()


def test_write_without_before_commit_drops_its_events(session: Session) -> None:
    with SqlaUnitOfWork(session, MagicMock()).write():
        SessionChangeRecorder(session).record(PhraseChanged(1))

    assert SessionChangeRecorder(session).drain() == ()


def test_events_recorded_outside_a_write_wait_for_the_next_write(session: Session) -> None:
    seen = _Seen()
    SessionChangeRecorder(session).record(DecisionChanged("run"))

    with SqlaUnitOfWork(session, MagicMock(), before_commit=seen).write():
        SessionChangeRecorder(session).record(PhraseChanged(1))

    assert seen.calls == [(DecisionChanged("run"), PhraseChanged(1))]
