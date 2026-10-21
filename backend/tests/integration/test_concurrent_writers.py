"""Worker jobs and an app request write the same database file at once, each on its own
session: every write goes through the unit of work, so none of them is lost."""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import backend.infrastructure.persistence.models  # noqa: F401  registers every table on Base
import pytest
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.database import Base, create_session_factory
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.session_work import SessionWork
from backend.infrastructure.persistence.sqla_job_queue import SqlaJobQueue
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SOURCE_ID = 1
COUNTER = "writes"
WRITES_EACH = 20
# Wide enough for another writer to come between a read and its write, were it allowed to.
BETWEEN_READ_AND_WRITE_S = 0.002
WRITERS = 3


class _Counter:
    """Adds one to a stored number: a read, then a write of what was read plus one."""

    def __init__(self, session: Session) -> None:
        self._settings = SqlaSettingsRepository(session, SessionChangeRecorder(session))
        self._unit_of_work = SqlaUnitOfWork(session, MagicMock())

    def add_one(self) -> None:
        with self._unit_of_work.write():
            seen = int(self._settings.get(COUNTER, "0") or "0")
            time.sleep(BETWEEN_READ_AND_WRITE_S)
            self._settings.set(COUNTER, str(seen + 1))


@pytest.fixture()
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    session_factory = create_session_factory(f"sqlite:///{tmp_path / 'shared.db'}")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        session.execute(text(
            "INSERT INTO sources (id, title, status, created_at)"
            " VALUES (:id, 'source', 'done', '2026-01-01 00:00:00')"
        ), {"id": SOURCE_ID})
        SqlaJobRepository(session, SessionChangeRecorder(session)).enqueue([
            Job.queued(JobType.TOPIC_TARGETS, SOURCE_ID, None),
            Job.queued(JobType.VIDEO_DOWNLOAD, SOURCE_ID, None),
        ])
        session.commit()
    yield session_factory
    session_factory.kw["bind"].dispose()


def _worker_job(queue: SqlaJobQueue, start: threading.Barrier) -> Callable[[], None]:
    def run() -> None:
        jobs = queue.claim_next_run({})
        assert jobs, "each worker job finds one to claim"
        start.wait()
        with queue.claimed(jobs, _Counter) as counter:
            for _ in range(WRITES_EACH):
                counter.add_one()
        queue.complete(jobs)
    return run


def _app_request(factory: sessionmaker[Session], start: threading.Barrier) -> Callable[[], None]:
    def run() -> None:
        with factory() as session:
            counter = _Counter(session)
            start.wait()
            for _ in range(WRITES_EACH):
                counter.add_one()
    return run


def test_no_write_is_lost(factory: sessionmaker[Session]) -> None:
    queue = SqlaJobQueue(SessionWork(factory, lambda s: SqlaUnitOfWork(s, MagicMock())))
    start = threading.Barrier(WRITERS)
    errors: list[BaseException] = []

    def guarded(work: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                work()
            except BaseException as exc:
                errors.append(exc)
                start.abort()
        return run

    threads = [
        threading.Thread(target=guarded(work))
        for work in (
            _worker_job(queue, start), _worker_job(queue, start), _app_request(factory, start),
        )
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    with factory() as session:
        assert SqlaSettingsRepository(
            session, SessionChangeRecorder(session),
        ).get(COUNTER) == str(WRITERS * WRITES_EACH)
        assert SqlaJobRepository(
            session, SessionChangeRecorder(session),
        ).get_jobs_by_status(list(JobStatus)) == []
