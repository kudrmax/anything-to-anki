"""A change of level or threshold rebuilds every source in the background, one by one."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.background_rebuild_launcher import (
    BackgroundSourcesRebuildLauncher,
    RebuildPasses,
)
from backend.infrastructure.api.source_operations import SourceOperationRegistry
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.source_rebuild_support import SOURCE, Bench, at, document, word

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

OTHER_SOURCE = 2


@pytest.fixture
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def _two_processed_sources(bench: Bench) -> None:
    bench.session.execute(text(
        "INSERT INTO sources (id, title, status, role, created_at)"
        " VALUES (:id, 'other', 'new', 'content', '2026-01-01 00:00:00')"
    ), {"id": OTHER_SOURCE})
    SqlaDocumentRepository(bench.session).save(OTHER_SOURCE, document())
    bench.session.commit()
    bench.analysis = [word("glare", at(0), at(1))]
    for source_id in (SOURCE, OTHER_SOURCE):
        process = bench.process()
        process.start(source_id)
        bench.session.commit()
        process.execute(source_id)
    bench.session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    bench.session.commit()


def _launcher(bench: Bench) -> BackgroundSourcesRebuildLauncher:
    return BackgroundSourcesRebuildLauncher(
        session_factory=lambda: bench.session,  # type: ignore[arg-type,return-value]
        rebuild_use_case=lambda _session: bench.rebuild(),
        operations=SourceOperationRegistry(),
        spawn=lambda work: work(),
        passes=RebuildPasses(),
    )


def _sections_of(bench: Bench, source_id: int) -> set[str | None]:
    bench.session.expire_all()
    return {
        row[0] for row in bench.session.execute(text(
            "SELECT p.earned_section FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
            " WHERE c.source_id = :id"
        ), {"id": source_id})
    }


def test_every_source_is_rebuilt(bench: Bench) -> None:
    _two_processed_sources(bench)
    assert _sections_of(bench, SOURCE) == {"extra"}

    _launcher(bench).rebuild_all()

    assert _sections_of(bench, SOURCE) == {"ready"}
    assert _sections_of(bench, OTHER_SOURCE) == {"ready"}


def test_a_busy_source_is_skipped_and_the_rest_is_rebuilt(bench: Bench) -> None:
    _two_processed_sources(bench)
    assert bench.lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    bench.session.commit()

    _launcher(bench).rebuild_all()

    assert _sections_of(bench, SOURCE) == {"extra"}
    assert _sections_of(bench, OTHER_SOURCE) == {"ready"}
    assert bench.lock.held(SOURCE) is SourceOperationKind.PROCESS


def test_no_source_is_locked_before_its_turn(bench: Bench) -> None:
    _two_processed_sources(bench)
    seen: list[SourceOperationKind | None] = []
    inner = bench.rebuild()
    original_run: Callable[..., object] = inner.run

    def run(source_id: int, include_open: bool) -> object:
        other = OTHER_SOURCE if source_id == SOURCE else SOURCE
        seen.append(bench.lock.held(other))
        return original_run(source_id, include_open)

    inner.run = run  # type: ignore[method-assign,assignment]
    launcher = BackgroundSourcesRebuildLauncher(
        session_factory=lambda: bench.session,  # type: ignore[arg-type,return-value]
        rebuild_use_case=lambda _session: inner,
        operations=SourceOperationRegistry(),
        spawn=lambda work: work(),
        passes=RebuildPasses(),
    )

    launcher.rebuild_all()

    assert seen[0] is None


def test_the_patch_does_not_wait_for_the_rebuild(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.infrastructure.api.app import app
    from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
    from fastapi.testclient import TestClient

    release = threading.Event()
    started = threading.Event()

    def blocked(_self: BackgroundSourcesRebuildLauncher) -> None:
        started.set()
        release.wait(timeout=10)

    monkeypatch.setattr(BackgroundSourcesRebuildLauncher, "_rebuild_each", blocked)

    def override_session():  # type: ignore[no-untyped-def]  # noqa: ANN202
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    try:
        with TestClient(app) as client:
            response = client.patch("/api/settings", json={"cefr_level": "C1"})
            assert response.status_code == 200
            assert response.json()["cefr_level"] == "C1"
            assert started.wait(timeout=10)
            assert not release.is_set()
            release.set()
    finally:
        release.set()
        app.dependency_overrides.clear()


def test_calls_close_together_never_overlap_and_a_full_pass_follows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inside = threading.Lock()
    first_started = threading.Event()
    release_first = threading.Event()
    done = threading.Event()
    overlaps: list[bool] = []
    passes: list[int] = []

    def one_pass(_self: BackgroundSourcesRebuildLauncher) -> None:
        overlaps.append(not inside.acquire(blocking=False))
        passes.append(len(passes) + 1)
        if len(passes) == 1:
            first_started.set()
            release_first.wait(timeout=10)
        else:
            done.set()
        if not overlaps[-1]:
            inside.release()

    monkeypatch.setattr(BackgroundSourcesRebuildLauncher, "_rebuild_each", one_pass)
    launcher = BackgroundSourcesRebuildLauncher(
        session_factory=MagicMock(), rebuild_use_case=MagicMock(),
        operations=SourceOperationRegistry(), passes=RebuildPasses(),
    )

    launcher.rebuild_all()
    assert first_started.wait(timeout=10)
    launcher.rebuild_all()
    launcher.rebuild_all()
    release_first.set()

    assert done.wait(timeout=10)
    assert passes == [1, 2]
    assert overlaps == [False, False]
