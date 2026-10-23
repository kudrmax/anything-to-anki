"""A long operation cut off by the app being killed leaves the sources as they were before
it: killed while analysing or inside its write, nothing of it is written. Its lock is left
behind and goes at the next start, after which the sources are processed as usual."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.persistence.database import (
    Base,
    create_session_factory,
    release_long_operation_lock,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_long_operation_lock import SqlaLongOperationLock
from sqlalchemy import text

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SOURCES = (1, 2)
TEXTS = (
    "The relentless rain never stopped, and the villagers grew weary of the gloom.",
    "She scrutinized the ledger with meticulous care before signing the contract.",
)
REACH_THE_STOP_S = 120
CHILD = "tests.integration.long_operation_crash_child"


def _database(path: Path) -> sessionmaker[Session]:
    factory = create_session_factory(f"sqlite:///{path}")
    Base.metadata.create_all(factory.kw["bind"])
    with factory() as session:
        for source_id, line in zip(SOURCES, TEXTS, strict=True):
            session.execute(text(
                "INSERT INTO sources (id, title, status, role, created_at)"
                " VALUES (:id, 'title', 'new', 'content', '2026-01-01 00:00:00')"
            ), {"id": source_id})
            SqlaDocumentRepository(session).save(source_id, Document((
                Paragraph(lines=(Line(line),), mode=ParagraphMode.FLOW),
            )))
        session.commit()
    return factory


def _kill_at(stop_at: str, db: Path, marker: Path) -> None:
    """Processes the sources in another process and kills it once it reaches `stop_at`."""
    child = subprocess.Popen(  # noqa: S603 — the test's own interpreter and module
        [sys.executable, "-m", CHILD, str(db), stop_at, str(marker), *map(str, SOURCES)],
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    try:
        deadline = time.monotonic() + REACH_THE_STOP_S
        while not marker.exists():
            assert child.poll() is None, f"the operation ended on its own: {child.returncode}"
            assert time.monotonic() < deadline, f"the operation never reached {stop_at}"
            time.sleep(0.05)
        child.send_signal(signal.SIGKILL)
    finally:
        child.wait()


def _statuses(factory: sessionmaker[Session]) -> list[str]:
    with factory() as session:
        return list(session.scalars(text("SELECT status FROM sources ORDER BY id")))


def _phrases(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        return int(session.scalar(text("SELECT COUNT(*) FROM phrases")) or 0)


def _lock_held(factory: sessionmaker[Session]) -> bool:
    with factory() as session:
        return SqlaLongOperationLock(session).held()


@pytest.mark.parametrize("stop_at", ["analyse", "apply"])
def test_a_killed_operation_writes_nothing_and_its_lock_goes_at_the_next_start(
    tmp_path: Path, stop_at: str,
) -> None:
    db = tmp_path / "app.db"
    factory = _database(db)

    _kill_at(stop_at, db, tmp_path / "reached")

    assert _statuses(factory) == ["new", "new"]
    assert _phrases(factory) == 0
    assert _lock_held(factory), "the lock outlives the killed process"

    release_long_operation_lock(factory)

    assert not _lock_held(factory)
