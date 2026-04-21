from __future__ import annotations

import json
from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel, StoredCandidateModel
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def _db_engine() -> Generator[object, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_db_engine: object) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=_db_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_db_engine: object) -> Generator[TestClient, None, None]:
    test_session_factory = sessionmaker(bind=_db_engine)

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

    def test_update_status_to_partially_reviewed(self, client: TestClient) -> None:
        create = client.post("/sources", json={"raw_text": "Some text"})
        source_id = create.json()["id"]
        response = client.patch(
            f"/sources/{source_id}/status", json={"status": "partially_reviewed"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "partially_reviewed"

    def test_update_status_to_reviewed(self, client: TestClient) -> None:
        create = client.post("/sources", json={"raw_text": "Some text"})
        source_id = create.json()["id"]
        response = client.patch(f"/sources/{source_id}/status", json={"status": "reviewed"})
        assert response.status_code == 200
        assert response.json()["status"] == "reviewed"

    def test_update_status_invalid_transition(self, client: TestClient) -> None:
        create = client.post("/sources", json={"raw_text": "Some text"})
        source_id = create.json()["id"]
        response = client.patch(f"/sources/{source_id}/status", json={"status": "processing"})
        assert response.status_code == 400

    def test_update_status_not_found(self, client: TestClient) -> None:
        response = client.patch("/sources/999/status", json={"status": "reviewed"})
        assert response.status_code == 404

    def test_get_source_candidates_include_frequency_band_and_usage(
        self, client: TestClient, db_session: Session,
    ) -> None:
        source = SourceModel(raw_text="Test text", status="done")
        db_session.add(source)
        db_session.flush()

        candidate = StoredCandidateModel(
            source_id=source.id,
            lemma="gonna",
            pos="VERB",
            cefr_level="B1",
            zipf_frequency=3.8,
            is_sweet_spot=True,
            context_fragment="I'm gonna do it",
            fragment_purity="clean",
            occurrences=1,
            status="pending",
            usage_distribution_json=json.dumps({"informal": 0.8, "neutral": 0.2}),
        )
        db_session.add(candidate)
        db_session.commit()

        response = client.get(f"/sources/{source.id}")
        assert response.status_code == 200
        data = response.json()
        candidates = data["candidates"]
        assert len(candidates) == 1

        c = candidates[0]
        assert c["frequency_band"] == "MID"
        assert c["usage_distribution"] == {"informal": 0.8, "neutral": 0.2}
