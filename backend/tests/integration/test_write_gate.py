"""While a level change holds its lock, a write refuses or waits, by the gate of its process;
the level change's own write goes through."""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.exceptions import LevelChangeInProgressError
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage
from backend.infrastructure.persistence.database import Base, create_session_factory
from backend.infrastructure.persistence.models import AIUsageModel, SettingModel
from backend.infrastructure.persistence.session_ai_usage_recorder import SessionAIUsageRecorder
from backend.infrastructure.persistence.sqla_level_change_lock import SqlaLevelChangeLock
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.write_gate import (
    OwnLevelChange,
    RefuseDuringLevelChange,
    WaitOutLevelChange,
    WriteGate,
)
from sqlalchemy import func, select

from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

LOCK_HELD_S = 1.0
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
        SqlaLevelChangeLock(session).take()
        session.commit()


def _unlock(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        SqlaLevelChangeLock(session).release()
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

    with factory() as session, pytest.raises(LevelChangeInProgressError):
        _write(session, RefuseDuringLevelChange(), "refused")

    assert _stored(factory) is None
    with factory() as session:
        _write(session, OwnLevelChange(), "own")  # the database is not left locked


def test_wait_gate_writes_after_release(factory: sessionmaker[Session]) -> None:
    _lock(factory)
    gate = WaitOutLevelChange()
    releaser = threading.Timer(LOCK_HELD_S, _unlock, args=(factory,))
    releaser.start()
    started = time.monotonic()

    with factory() as session:
        _write(session, gate, "waited")
    elapsed = time.monotonic() - started

    releaser.join()
    assert _stored(factory) == "waited"
    assert elapsed >= LOCK_HELD_S
    assert gate.waited_seconds() >= LOCK_HELD_S * 0.9


def test_own_gate_writes_while_locked(factory: sessionmaker[Session]) -> None:
    _lock(factory)

    with factory() as session:
        _write(session, OwnLevelChange(), "own")

    assert _stored(factory) == "own"


@pytest.mark.parametrize(
    "gate", [RefuseDuringLevelChange(), WaitOutLevelChange(), OwnLevelChange()],
)
def test_any_gate_writes_when_unlocked(factory: sessionmaker[Session], gate: WriteGate) -> None:
    with factory() as session:
        _write(session, gate, "free")

    assert _stored(factory) == "free"


def test_default_gate_refuses(factory: sessionmaker[Session]) -> None:
    _lock(factory)

    with (
        factory() as session,
        pytest.raises(LevelChangeInProgressError),
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
