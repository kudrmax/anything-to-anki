from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine)

    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_session_factory() -> object:
        return test_session_factory

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = override_session_factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestSourcesAPI:
    def test_create_source(self, client: TestClient) -> None:
        response = client.post("/sources", json={"raw_text": "Hello world"})
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] == "new"

    def test_create_empty_source(self, client: TestClient) -> None:
        response = client.post("/sources", json={"raw_text": ""})
        assert response.status_code == 400

    def test_list_sources(self, client: TestClient) -> None:
        client.post("/sources", json={"raw_text": "Text one"})
        client.post("/sources", json={"raw_text": "Text two"})
        response = client.get("/sources")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_source(self, client: TestClient) -> None:
        create = client.post("/sources", json={"raw_text": "Hello"})
        source_id = create.json()["id"]
        response = client.get(f"/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["raw_text"] == "Hello"

    def test_get_source_not_found(self, client: TestClient) -> None:
        response = client.get("/sources/999")
        assert response.status_code == 404

    def test_process_returns_202(self, client: TestClient) -> None:
        create = client.post("/sources", json={"raw_text": "The quick brown fox"})
        source_id = create.json()["id"]
        response = client.post(f"/sources/{source_id}/process")
        assert response.status_code == 202

    def test_process_not_found(self, client: TestClient) -> None:
        response = client.post("/sources/999/process")
        assert response.status_code == 404
