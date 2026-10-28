from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import UpdateProgress, UpdateState
from backend.infrastructure.api import dependencies
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import LongOperationLockModel
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tests.release_support import FakeInstalledRelease, FakeReleaseSource, changelog

if TYPE_CHECKING:
    from collections.abc import Generator

INSTALLED_VERSION = "1.0.0"
IMAGE_PATH = "docs/images/changelog/1.0.0/shot.png"
IMAGE_BYTES = b"\x89PNG-installed"
REMOTE_IMAGE_PATH = "docs/images/changelog/1.1.0/shot.png"
REMOTE_IMAGE_BYTES = b"\x89PNG-remote"
IMAGE_TEXT = (
    "# Changelog\n\n## 1.0.0 — 2026-10-01\n\nFirst.\n\n### Big feature\n\n"
    f"Text with **bold**.\n\n![shot]({IMAGE_PATH})\n"
)


class _NoUpdateRunner(UpdateRunner):
    """Never spawns anything: counts the starts and reports the state it is given."""

    def __init__(self) -> None:
        self.started = 0
        self.current = UpdateState.IDLE

    def start(self) -> None:
        self.started += 1

    def state(self) -> UpdateProgress:
        return UpdateProgress(self.current)


@pytest.fixture()
def factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def runner() -> _NoUpdateRunner:
    return _NoUpdateRunner()


@pytest.fixture()
def client(
    factory: sessionmaker[Session],
    runner: _NoUpdateRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    container = dependencies.get_container()
    monkeypatch.setattr(
        container,
        "_installed_release",
        FakeInstalledRelease(INSTALLED_VERSION, IMAGE_TEXT, {IMAGE_PATH: IMAGE_BYTES}),
    )
    monkeypatch.setattr(
        container,
        "_release_source",
        FakeReleaseSource(
            "1.1.0",
            changelog("1.0.0", "1.1.0"),
            {f"1.1.0/{REMOTE_IMAGE_PATH}": REMOTE_IMAGE_BYTES},
        ),
    )
    monkeypatch.setattr(container, "_update_runner", runner)

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.integration
def test_version_is_the_installed_one(client: TestClient) -> None:
    assert client.get("/api/version").json() == {"version": INSTALLED_VERSION}


@pytest.mark.integration
def test_unseen_on_a_fresh_database_is_empty(client: TestClient) -> None:
    response = client.get("/api/changelog/unseen")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
def test_seen_is_accepted_without_content(client: TestClient) -> None:
    assert client.post("/api/changelog/seen").status_code == 204


@pytest.mark.integration
def test_section_markdown_becomes_html_with_image_sources_pointing_at_the_api(
    client: TestClient,
) -> None:
    section = client.get("/api/changelog").json()[0]["sections"][0]

    assert "html" in section
    assert "body_markdown" not in section
    assert "<strong>bold</strong>" in section["html"]
    assert f'src="/api/changelog/assets/1.0.0/{IMAGE_PATH}"' in section["html"]


@pytest.mark.integration
def test_installed_image_is_served_from_disk(client: TestClient) -> None:
    response = client.get(f"/api/changelog/assets/1.0.0/{IMAGE_PATH}")

    assert response.status_code == 200
    assert response.content == IMAGE_BYTES
    assert response.headers["content-type"] == "image/png"


@pytest.mark.integration
def test_other_version_image_comes_from_the_release_source(client: TestClient) -> None:
    response = client.get(f"/api/changelog/assets/1.1.0/{REMOTE_IMAGE_PATH}")

    assert response.status_code == 200
    assert response.content == REMOTE_IMAGE_BYTES


@pytest.mark.integration
@pytest.mark.parametrize(
    "url",
    [
        "/api/changelog/assets/1.0.0/pyproject.toml",
        "/api/changelog/assets/1.0.0/docs/images/changelog/1.0.0/missing.png",
        "/api/changelog/assets/1.2.0/docs/images/changelog/1.2.0/shot.png",
        "/api/changelog/assets/latest/docs/images/changelog/1.0.0/shot.png",
    ],
)
def test_asset_not_found_is_404(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 404


@pytest.mark.integration
def test_updates_lists_the_changes_with_html(client: TestClient) -> None:
    status = client.get("/api/updates", params={"force": "true"}).json()

    assert (status["current"], status["latest"], status["available"]) == ("1.0.0", "1.1.0", True)
    assert [entry["version"] for entry in status["entries"]] == ["1.1.0"]
    assert "<li>" in status["entries"][0]["sections"][0]["html"]


@pytest.mark.integration
def test_update_starts_and_state_is_readable(client: TestClient, runner: _NoUpdateRunner) -> None:
    assert client.post("/api/update").status_code == 202
    assert runner.started == 1
    assert client.get("/api/update/state").json() == {"state": "idle", "log_tail": ""}


@pytest.mark.integration
def test_update_during_a_long_operation_is_423(
    client: TestClient, factory: sessionmaker[Session], runner: _NoUpdateRunner,
) -> None:
    with factory() as session:
        session.add(LongOperationLockModel(id=1, started_at=datetime.now(tz=UTC)))
        session.commit()

    assert client.post("/api/update").status_code == 423
    assert runner.started == 0


@pytest.mark.integration
def test_update_while_one_runs_is_409(client: TestClient, runner: _NoUpdateRunner) -> None:
    runner.current = UpdateState.RUNNING

    assert client.post("/api/update").status_code == 409
    assert runner.started == 0
