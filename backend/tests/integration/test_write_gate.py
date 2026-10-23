"""While a level change holds its lock, a write refuses or waits, by the gate of its process;
the level change's own write goes through."""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.database import Base, create_session_factory
from backend.infrastructure.persistence.models import AIUsageModel, SettingModel
from backend.infrastructure.persistence.session_ai_usage_recorder import SessionAIUsageRecorder
from backend.infrastructure.persistence.sqla_long_operation_lock import SqlaLongOperationLock
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.write_gate import (
    GATE_RETRY_SECONDS,
    OwnLongOperation,
    RefuseDuringLongOperation,
    WaitOutLongOperation,
    WriteGate,
)
from sqlalchemy import func, select

from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

LOCK_HELD_S = 1.0
WAITS_BEFORE_RELEASE = 2
KEY = "probe"


@pytest.fixture()
def factory(tmp_path: Path) -> sessionmaker[Session]:
    made = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(made.kw["bind"])
    return made


def _unit_of_work(session: Session, gate: WriteGate) -> SqlaUnitOfWork:
    return SqlaUnitOfWork(session, user_vocabulary().scope, gate=gate)


def _lock(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        SqlaLongOperationLock(session).take()
        session.commit()


def _unlock(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        SqlaLongOperationLock(session).release()
        session.commit()


def _write(session: Session, gate: WriteGate, value: str) -> None:
    with _unit_of_work(session, gate).write():
        session.merge(SettingModel(key=KEY, value=value))


def _stored(factory: sessionmaker[Session]) -> str | None:
    with factory() as session:
        return session.scalar(select(SettingModel.value).where(SettingModel.key == KEY))


def test_refuse_gate_raises_while_locked_and_rolls_back(
    factory: sessionmaker[Session],
) -> None:
    _lock(factory)

    with factory() as session, pytest.raises(LongOperationInProgressError):
        _write(session, RefuseDuringLongOperation(), "refused")

    assert _stored(factory) is None
    with factory() as session:
        _write(session, OwnLongOperation(), "own")  # the database is not left locked


def test_wait_gate_writes_after_release_and_counts_its_waits(
    factory: sessionmaker[Session],
) -> None:
    """The lock is let go once the write has started its second wait: the write lands
    after it, and every wait counts, however slow the first look at the lock was."""
    _lock(factory)
    waits = threading.Semaphore(0)

    class _Counted(WaitOutLongOperation):
        def wait(self) -> None:
            waits.release()
            super().wait()

    gate = _Counted()

    def release_on_the_second_wait() -> None:
        for _ in range(WAITS_BEFORE_RELEASE):
            waits.acquire()
        _unlock(factory)

    releaser = threading.Thread(target=release_on_the_second_wait)
    releaser.start()

    with factory() as session:
        _write(session, gate, "waited")

    releaser.join()
    assert _stored(factory) == "waited"
    assert gate.waited_seconds() >= WAITS_BEFORE_RELEASE * GATE_RETRY_SECONDS


def test_own_gate_writes_while_locked(factory: sessionmaker[Session]) -> None:
    _lock(factory)

    with factory() as session:
        _write(session, OwnLongOperation(), "own")

    assert _stored(factory) == "own"


@pytest.mark.parametrize(
    "gate", [RefuseDuringLongOperation(), WaitOutLongOperation(), OwnLongOperation()],
)
def test_any_gate_writes_when_unlocked(factory: sessionmaker[Session], gate: WriteGate) -> None:
    with factory() as session:
        _write(session, gate, "free")

    assert _stored(factory) == "free"


def test_default_gate_refuses(factory: sessionmaker[Session]) -> None:
    _lock(factory)

    with (
        factory() as session,
        pytest.raises(LongOperationInProgressError),
        SqlaUnitOfWork(session, user_vocabulary().scope).write(),
    ):
        session.merge(SettingModel(key=KEY, value="default"))


def test_ai_usage_record_waits_out_the_lock(factory: sessionmaker[Session]) -> None:
    """The record is written beside every gate; it waits rather than meet the level
    change's write and its busy timeout."""
    _lock(factory)
    releaser = threading.Timer(LOCK_HELD_S, _unlock, args=(factory,))
    releaser.start()
    started = time.monotonic()

    SessionAIUsageRecorder(factory).record(AIUsageRecord(
        feature=AIFeature.MEANING_BATCH, model="claude-x",
        usage=TokenUsage(input_tokens=1, output_tokens=2, cache_read_tokens=0,
                         cache_creation_tokens=0),
        item_count=1, duration_ms=10, succeeded=True, created_at=datetime.now(tz=UTC),
    ))
    elapsed = time.monotonic() - started

    releaser.join()
    assert elapsed >= LOCK_HELD_S
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AIUsageModel)) == 1


SHORT_BUSY_TIMEOUT_MS = 200
STAGE_TWO_S = 1.0


@pytest.fixture()
def short_busy_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    """A database whose busy timeout is far shorter than the level change's one write, as
    30 s is on a whole book."""
    monkeypatch.setattr(database, "SQLITE_BUSY_TIMEOUT_MS", SHORT_BUSY_TIMEOUT_MS)
    made = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(made.kw["bind"])
    return made


def _stage_two(factory: sessionmaker[Session], inside: threading.Event) -> None:
    """The level change's one write: held past the busy timeout, dropping the lock at its
    commit."""
    with factory() as session, _unit_of_work(session, OwnLongOperation()).write():
        inside.set()
        time.sleep(STAGE_TWO_S)
        SqlaLongOperationLock(session).release()


@pytest.mark.parametrize("gate", [WaitOutLongOperation(), RefuseDuringLongOperation()])
def test_a_write_during_the_long_write_meets_the_gate_not_the_busy_timeout(
    short_busy_factory: sessionmaker[Session], gate: WriteGate,
) -> None:
    _lock(short_busy_factory)
    inside = threading.Event()
    change = threading.Thread(target=_stage_two, args=(short_busy_factory, inside))
    change.start()
    inside.wait()

    try:
        with short_busy_factory() as session:
            _write(session, gate, "after")
    except LongOperationInProgressError:
        assert isinstance(gate, RefuseDuringLongOperation)
    else:
        assert isinstance(gate, WaitOutLongOperation)
        assert _stored(short_busy_factory) == "after"
    finally:
        change.join()
