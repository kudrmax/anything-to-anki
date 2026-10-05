from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.exceptions import CandidateNotFoundError
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import Generator


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
class TestEnqueueCandidateTTS:
    def test_returns_202_and_queues_the_card(self, client: TestClient) -> None:
        use_case = _get_mock_container().enqueue_candidate_tts_use_case.return_value

        response = client.post("/candidates/1/generate-tts")

        assert response.status_code == 202
        assert response.json() == {"status": "enqueued"}
        use_case.execute.assert_called_once_with(1)

    def test_returns_404_for_missing_candidate(self, client: TestClient) -> None:
        use_case = _get_mock_container().enqueue_candidate_tts_use_case.return_value
        use_case.execute.side_effect = CandidateNotFoundError(9999)

        response = client.post("/candidates/9999/generate-tts")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
