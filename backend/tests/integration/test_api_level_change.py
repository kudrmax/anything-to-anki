"""Over HTTP: saving a new level starts the change and answers at once; while it runs,
reads work, every write answers 423, and the change can be cancelled."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api import running_operations, source_operations
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.api.source_operations import SourceOperationRegistry
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from tests.integration.conftest import insert_source

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from backend.application.dto.settings_dtos import UpdateSettingsRequest
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LOCKED = 423


class _HeldChange:
    """The change's thread, held until the test lets it run."""

    def __init__(self) -> None:
        self.pending: Callable[[], None] | None = None

    def run(self) -> None:
        assert self.pending is not None
        pending, self.pending = self.pending, None
        pending()


@pytest.fixture()
def factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def held(monkeypatch: pytest.MonkeyPatch, factory: sessionmaker[Session]) -> _HeldChange:
    change = _HeldChange()

    def run_on_test_db(container: Container) -> Callable[[UpdateSettingsRequest], None]:
        def run(request: UpdateSettingsRequest) -> None:
            with factory() as session:
                container.change_level_use_case(session).execute(request)

        return run

    def hold(_self: Container, run: Callable[[], None]) -> None:
        change.pending = run

    monkeypatch.setattr(Container, "_spawn_level_change", hold)
    monkeypatch.setattr(Container, "_level_change_run", run_on_test_db)
    return change


@pytest.fixture()
def client(
    held: _HeldChange, factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from backend.application.utils.long_operation_progress import LongOperationProgress
    from backend.infrastructure.api import dependencies

    container = dependencies.get_container()
    monkeypatch.setattr(container, "_long_operation_progress", LongOperationProgress())

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _status(client: TestClient) -> dict[str, object]:
    response = client.get("/api/long-operation")
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def test_patch_returns_at_once_and_status_runs(client: TestClient, held: _HeldChange) -> None:
    response = client.patch("/api/settings", json={"cefr_level": "C1"})

    assert response.status_code == 200
    assert response.json()["cefr_level"] == "B2"
    assert _status(client)["running"] is True

    held.run()

    status = _status(client)
    assert (status["running"], status["outcome"], status["percent"]) == (False, "succeeded", 100)
    assert client.get("/api/settings").json()["cefr_level"] == "C1"


def test_second_patch_during_change_is_refused(client: TestClient, held: _HeldChange) -> None:
    client.patch("/api/settings", json={"cefr_level": "C1"})

    assert client.patch("/api/settings", json={"cefr_level": "C2"}).status_code == LOCKED

    held.run()
    assert client.get("/api/settings").json()["cefr_level"] == "C1"


def test_write_endpoint_during_change_is_423(client: TestClient, held: _HeldChange) -> None:
    client.patch("/api/settings", json={"cefr_level": "C1"})

    response = client.patch("/api/settings", json={"anki_deck_name": "Other"})

    assert response.status_code == LOCKED
    held.run()
    assert client.get("/api/settings").json()["anki_deck_name"] == "Default"


def test_reads_work_during_change(client: TestClient, held: _HeldChange) -> None:
    client.patch("/api/settings", json={"cefr_level": "C1"})

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["cefr_level"] == "B2"
    held.run()


def test_cancel_endpoint(client: TestClient, held: _HeldChange) -> None:
    assert client.post("/api/long-operation/cancel").status_code == 409
    client.patch("/api/settings", json={"cefr_level": "C1", "anki_deck_name": "Other"})

    assert client.post("/api/long-operation/cancel").status_code == 202
    held.run()

    assert _status(client)["outcome"] == "cancelled"
    settings = client.get("/api/settings").json()
    assert (settings["cefr_level"], settings["anki_deck_name"]) == ("B2", "Default")
    assert client.patch("/api/settings", json={"anki_deck_name": "Free"}).status_code == 200


def test_non_trigger_patch_saves_directly(client: TestClient, held: _HeldChange) -> None:
    response = client.patch("/api/settings", json={"anki_deck_name": "Other"})

    assert response.status_code == 200
    assert response.json()["anki_deck_name"] == "Other"
    assert held.pending is None
    assert _status(client)["running"] is False


def test_busy_source_refuses_the_change(
    client: TestClient, held: _HeldChange, factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        insert_source(session, 1)
        SqlaSourceOperationLock(session).acquire(1, SourceOperationKind.PROCESS)
        session.commit()

    response = client.patch("/api/settings", json={"cefr_level": "C1"})

    assert response.status_code == 409
    assert held.pending is None
    assert _status(client)["running"] is False
    assert client.patch("/api/settings", json={"anki_deck_name": "Free"}).status_code == 200


def test_a_running_preview_refuses_the_change(
    client: TestClient, held: _HeldChange, monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = SourceOperationRegistry()
    registry.started("all", SourceOperationKind.PREVIEW)
    monkeypatch.setattr(source_operations.OPERATIONS, "_last", registry._last)

    response = client.patch("/api/settings", json={"cefr_level": "C1"})

    assert response.status_code == 409
    assert held.pending is None
    assert client.get("/api/settings").json()["cefr_level"] == "B2"


def test_a_running_index_build_refuses_the_change(
    client: TestClient, held: _HeldChange, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(running_operations.BOOTSTRAP_BUILDS, "running", lambda: True)

    response = client.patch("/api/settings", json={"cefr_level": "C1"})

    assert response.status_code == 409
    assert held.pending is None


def test_the_index_build_does_not_start_during_a_change(
    client: TestClient, held: _HeldChange,
) -> None:
    client.patch("/api/settings", json={"cefr_level": "C1"})

    assert client.post("/api/bootstrap/build").status_code == LOCKED

    held.run()
