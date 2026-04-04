from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
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

    # Seed test data
    session = test_session_factory()
    source = SourceModel(raw_text="Test", status="done")
    session.add(source)
    session.flush()
    repo = SqlaCandidateRepository(session)
    repo.create_batch([
        StoredCandidate(
            source_id=source.id, lemma="pursuit", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5, is_sweet_spot=True,
            context_fragment="the pursuit of", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        ),
    ])
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
class TestCandidatesAPI:
    def test_mark_candidate_learn(self, client: TestClient) -> None:
        response = client.patch("/candidates/1", json={"status": "learn"})
        assert response.status_code == 200
        assert response.json()["status"] == "learn"

    def test_mark_candidate_known(self, client: TestClient) -> None:
        response = client.patch("/candidates/1", json={"status": "known"})
        assert response.status_code == 200
        # Verify it was added to known words
        kw_response = client.get("/known-words")
        assert any(w["lemma"] == "pursuit" for w in kw_response.json())

    def test_mark_candidate_not_found(self, client: TestClient) -> None:
        response = client.patch("/candidates/999", json={"status": "learn"})
        assert response.status_code == 404

    def test_mark_candidate_invalid_status(self, client: TestClient) -> None:
        response = client.patch("/candidates/1", json={"status": "invalid"})
        assert response.status_code == 422
