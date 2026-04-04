from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import KnownWordModel
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

    # Seed
    session = test_session_factory()
    session.add(KnownWordModel(lemma="run", pos="VERB"))
    session.commit()
    session.close()

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
class TestKnownWordsAPI:
    def test_list(self, client: TestClient) -> None:
        response = client.get("/known-words")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lemma"] == "run"

    def test_delete(self, client: TestClient) -> None:
        response = client.delete("/known-words/1")
        assert response.status_code == 200
        response = client.get("/known-words")
        assert len(response.json()) == 0
