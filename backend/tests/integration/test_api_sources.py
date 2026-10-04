from __future__ import annotations

import json
from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

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

    def test_created_at_is_returned_with_utc_offset(self, client: TestClient) -> None:
        """Clients render times in the viewer's zone; they need the offset to do so."""
        before = datetime.now(tz=UTC)
        client.post("/sources", json={"raw_text": "Hello"})

        created_at = datetime.fromisoformat(client.get("/sources").json()[0]["created_at"])

        assert created_at.utcoffset() == timedelta(0)
        assert abs(created_at - before) < timedelta(minutes=1)

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


@pytest.mark.integration
class TestCreateFileSource:
    def test_text_file_creates_source(self, client: TestClient, tmp_path: Path) -> None:
        txt_file = tmp_path / "article.txt"
        txt_file.write_text("Hello world, this is a test article.", encoding="utf-8")

        resp = client.post("/sources/file", json={
            "file_path": str(txt_file),
            "title": "Test Article",
        })

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "new"

    def test_missing_file_returns_404(self, client: TestClient) -> None:
        resp = client.post("/sources/file", json={
            "file_path": "/nonexistent/file.txt",
        })

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.integration
class TestSavedPhrasesAPI:
    def test_phrase_goes_to_saved_phrases_source_to_learn(self, client: TestClient) -> None:
        response = client.post(
            "/sources/saved-phrases",
            json={"phrase": "She finally gave in to the pressure.", "target": "gave in"},
        )

        assert response.status_code == 201
        candidate = response.json()
        assert candidate["status"] == "learn"
        assert candidate["lemma"] == "give in"
        sources = client.get("/sources").json()
        assert len(sources) == 1
        saved_source = sources[0]
        assert saved_source["title"] == "Saved phrases"
        assert saved_source["content_type"] == "phrases"
        assert saved_source["is_permanent"] is True
        assert saved_source["learn_count"] == 1
        detail = client.get(f"/sources/{saved_source['id']}").json()
        assert detail["has_source_text"] is False
        assert detail["can_polish_phrases"] is False

    def test_second_phrase_reuses_the_same_source(self, client: TestClient) -> None:
        for phrase in ("It was a daunting task.", "Keep it concise."):
            target = phrase.split()[-1].rstrip(".")
            client.post("/sources/saved-phrases", json={"phrase": phrase, "target": target})

        sources = client.get("/sources").json()
        assert len(sources) == 1
        assert sources[0]["candidate_count"] == 2

    def test_target_outside_phrase_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/sources/saved-phrases",
            json={"phrase": "It was a daunting task.", "target": "challenge"},
        )
        assert response.status_code == 400

    def test_saved_phrases_source_cannot_be_deleted_or_reprocessed(
        self, client: TestClient,
    ) -> None:
        client.post(
            "/sources/saved-phrases",
            json={"phrase": "It was a daunting task.", "target": "daunting"},
        )
        source_id = client.get("/sources").json()[0]["id"]

        assert client.delete(f"/sources/{source_id}").status_code == 409
        assert client.post(f"/sources/{source_id}/reprocess").status_code == 409
