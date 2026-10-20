"""Update, Re-cut, their preview and Refresh of a set of sources: one source, a collection,
Unsorted or all of them, through endpoints that take the set's scope token."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Generator  # noqa: TC003

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.app import app
from backend.infrastructure.api.background import operation_background
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.api.routes import operations as operations_routes
from backend.infrastructure.api.source_operations import SourceOperationRegistry
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source

pytestmark = pytest.mark.integration

PILOT, FINALE, TOPIC = 1, 2, 3


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        for source_id in (PILOT, FINALE):
            insert_source(session, source_id)
        session.commit()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def operations(monkeypatch: pytest.MonkeyPatch) -> SourceOperationRegistry:
    """Sources of every test get the same ids: operations of one must not show in another."""
    registry = SourceOperationRegistry()
    monkeypatch.setattr(operations_routes, "OPERATIONS", registry)
    return registry


@pytest.fixture()
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Background operations started by the routes; none of them runs."""
    started: list[object] = []

    def record(work: Coroutine[object, object, None]) -> None:
        work.close()
        started.append(work)

    monkeypatch.setattr(operations_routes, "in_background", record)
    return started


def _show(client: TestClient) -> str:
    show = client.post("/collections", json={"name": "Show"}).json()
    client.post("/sources/placements", json={"placements": [
        {"source_id": PILOT, "collection_id": show["id"]},
        {"source_id": FINALE, "collection_id": show["id"]},
    ]})
    return str(show["id"])


def _rebuild(client: TestClient, scope: str, operation: str = "update") -> int:
    response = client.post(f"/api/operations/{operation}", params={"scope": scope})
    return response.status_code


def _preview(client: TestClient, scope: str, of: str = "update") -> int:
    response = client.post("/api/operations/preview", params={"scope": scope, "of": of})
    return response.status_code


def _hold(factory: sessionmaker[Session], *source_ids: int) -> None:
    with factory() as session:
        lock = SqlaSourceOperationLock(session)
        for source_id in source_ids:
            lock.acquire(source_id, SourceOperationKind.PROCESS)
        session.commit()


def _topic(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        session.execute(text(
            "INSERT INTO sources (id, title, status, role, topic_query, created_at)"
            " VALUES (:id, 'salary', 'done', 'topic', 'salary talk', '2026-01-01 00:00:00')"
        ), {"id": TOPIC})
        session.commit()


@pytest.mark.parametrize("operation", ["update", "recut"])
def test_a_source_is_updated_or_recut_in_the_background(
    client: TestClient, spawned: list[object], operation: str,
) -> None:
    started = client.post(f"/api/operations/{operation}", params={"scope": f"source-{PILOT}"})

    assert started.status_code == 202
    running = started.json()
    assert (running["kind"], running["state"]) == (operation, "running")
    assert len(spawned) == 1
    state = client.get("/api/operations", params={"scope": f"source-{PILOT}"})
    assert state.status_code == 200
    assert state.json()["operation_id"] == running["operation_id"]


def test_a_collection_previews_its_rebuild_in_the_background(
    client: TestClient, spawned: list[object],
) -> None:
    show = _show(client)

    started = client.post("/api/operations/preview", params={"scope": show, "of": "recut"})

    assert started.status_code == 202
    assert (started.json()["kind"], started.json()["state"]) == ("preview", "running")
    assert len(spawned) == 1
    assert client.get("/api/operations", params={"scope": show}).status_code == 200
    assert client.get("/api/operations", params={"scope": "all"}).status_code == 404


def test_all_is_rebuilt_without_a_scope_of_its_own(
    client: TestClient, spawned: list[object],
) -> None:
    assert _rebuild(client, "all") == 202
    assert _rebuild(client, "unsorted") == 202
    assert len(spawned) == 2


def test_a_set_starts_while_one_of_its_sources_is_free(
    client: TestClient, factory: sessionmaker[Session], spawned: list[object],
) -> None:
    show = _show(client)
    _hold(factory, PILOT)

    assert _rebuild(client, show) == 202


def test_a_set_whose_every_source_is_busy_is_409(
    client: TestClient, factory: sessionmaker[Session], spawned: list[object],
) -> None:
    show = _show(client)
    _hold(factory, PILOT, FINALE)

    assert _rebuild(client, show) == 409
    assert _preview(client, f"source-{PILOT}") == 409
    assert spawned == []


def test_a_set_without_a_source_to_rebuild_is_400(
    client: TestClient, spawned: list[object],
) -> None:
    empty = client.post("/collections", json={"name": "Empty"}).json()["id"]

    assert _rebuild(client, str(empty)) == 400
    assert spawned == []


def test_a_topic_alone_is_updated_but_not_recut(
    client: TestClient, factory: sessionmaker[Session], spawned: list[object],
) -> None:
    _topic(factory)
    topic = f"source-{TOPIC}"

    assert (_rebuild(client, topic, "recut"), _preview(client, topic, "recut")) == (400, 400)
    assert (_rebuild(client, topic), _preview(client, topic)) == (202, 202)


def test_a_preview_of_an_unknown_mode_is_422(client: TestClient) -> None:
    assert _preview(client, f"source-{PILOT}", "rebuild") == 422


def test_refresh_needs_a_topic_in_the_set(
    client: TestClient, factory: sessionmaker[Session], spawned: list[object],
) -> None:
    assert client.post("/api/operations/refresh", params={"scope": "all"}).status_code == 400
    _topic(factory)

    started = client.post("/api/operations/refresh", params={"scope": "all"})

    assert started.status_code == 202
    assert (started.json()["kind"], started.json()["state"]) == ("refresh", "running")
    assert client.post(
        "/api/operations/refresh", params={"scope": f"source-{PILOT}"},
    ).status_code == 400


def test_a_missing_set_is_404_and_a_bad_token_400(client: TestClient) -> None:
    assert _rebuild(client, "source-999") == 404
    assert _rebuild(client, "999") == 404
    assert client.get("/api/operations", params={"scope": "nonsense"}).status_code == 400


def test_a_set_with_no_operation_has_no_operation_state(client: TestClient) -> None:
    assert client.get("/api/operations", params={"scope": f"source-{PILOT}"}).status_code == 404


def test_an_operation_that_fails_to_start_running_ends_in_error(
    client: TestClient, factory: sessionmaker[Session], operations: SourceOperationRegistry,
) -> None:
    token = f"source-{PILOT}"
    operation = operations.started(token, SourceOperationKind.UPDATE)

    def broken(_session: Session) -> Callable[[], None]:
        raise RuntimeError("could not build the use case")

    asyncio.run(operation_background(
        operations, token, operation.operation_id, factory, broken,
    ))

    state = client.get("/api/operations", params={"scope": token}).json()
    assert (state["state"], state["error"]) == ("error", "could not build the use case")
