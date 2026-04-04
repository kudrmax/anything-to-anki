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
class TestSettingsAPI:
    def test_get_default(self, client: TestClient) -> None:
        response = client.get("/settings")
        assert response.status_code == 200
        assert response.json()["cefr_level"] == "B1"

    def test_update_and_get(self, client: TestClient) -> None:
        response = client.patch("/settings", json={"cefr_level": "C1"})
        assert response.status_code == 200
        assert response.json()["cefr_level"] == "C1"
        response = client.get("/settings")
        assert response.json()["cefr_level"] == "C1"

    def test_update_invalid_level(self, client: TestClient) -> None:
        response = client.patch("/settings", json={"cefr_level": "X9"})
        assert response.status_code == 422
