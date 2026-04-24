from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_container, get_db_session, get_session_factory
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

    mock_container = MagicMock()

    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_session_factory() -> object:
        return test_session_factory

    def override_container() -> MagicMock:
        return mock_container

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = override_session_factory
    app.dependency_overrides[get_container] = override_container
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _get_mock_container() -> MagicMock:
    """Retrieve the mock container from the app overrides."""
    return app.dependency_overrides[get_container]()


@pytest.mark.unit
class TestEnqueueTTSGeneration:
    def test_returns_202_with_enqueued_count(self, client: TestClient) -> None:
        mock_container = _get_mock_container()
        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = [1, 2, 3]
        mock_container.enqueue_tts_generation_use_case.return_value = mock_use_case

        response = client.post("/sources/10/tts/generate")

        assert response.status_code == 202
        assert response.json() == {"enqueued": 3}

    def test_returns_zero_when_no_eligible(self, client: TestClient) -> None:
        mock_container = _get_mock_container()
        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = []
        mock_container.enqueue_tts_generation_use_case.return_value = mock_use_case

        response = client.post("/sources/99/tts/generate")

        assert response.status_code == 202
        assert response.json() == {"enqueued": 0}


@pytest.mark.unit
class TestEnqueueCandidateTTS:
    def test_returns_202_for_valid_candidate(self, client: TestClient) -> None:
        mock_container = _get_mock_container()
        mock_job_repo = MagicMock()
        mock_container.job_repository.return_value = mock_job_repo

        # Insert a real candidate into the in-memory DB
        from backend.infrastructure.persistence.models import StoredCandidateModel

        session_factory = app.dependency_overrides[get_session_factory]()
        session = session_factory()
        session.add(StoredCandidateModel(
            id=1,
            source_id=10,
            lemma="test",
            pos="NOUN",
            zipf_frequency=4.0,
            is_sweet_spot=True,
            context_fragment="a test",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.LEARN.value,
        ))
        session.commit()
        session.close()

        response = client.post("/candidates/1/generate-tts")

        assert response.status_code == 202
        assert response.json() == {"status": "enqueued"}

    def test_returns_404_for_missing_candidate(self, client: TestClient) -> None:
        response = client.post("/candidates/9999/generate-tts")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
