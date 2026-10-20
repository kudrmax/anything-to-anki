from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.exceptions import PhraseNotFoundError, SourceOperationBusyError
from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp
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


BUSY = SourceOperationBusyError(1, "rebuild")


@pytest.mark.unit
class TestGenerationOfAPhrase:
    @pytest.mark.parametrize(("path", "use_case"), [
        ("/phrases/7/generate-tts", "enqueue_phrase_tts_use_case"),
        ("/phrases/7/polish", "enqueue_phrase_polish_use_case"),
        ("/phrases/7/regenerate-media", "regenerate_phrase_media_use_case"),
    ])
    def test_works_on_the_phrase(self, client: TestClient, path: str, use_case: str) -> None:
        called = getattr(_get_mock_container(), use_case).return_value

        response = client.post(path)

        assert response.status_code == 202
        called.execute.assert_called_once_with(7)

    @pytest.mark.parametrize(("path", "use_case", "error", "status"), [
        ("/phrases/7/generate-tts", "enqueue_phrase_tts_use_case", BUSY, 409),
        ("/phrases/7/generate-tts", "enqueue_phrase_tts_use_case", PhraseNotFoundError(7), 404),
        ("/phrases/7/polish", "enqueue_phrase_polish_use_case", BUSY, 409),
        ("/phrases/7/polish", "enqueue_phrase_polish_use_case", PhraseNotFoundError(7), 404),
        ("/phrases/7/regenerate-media", "regenerate_phrase_media_use_case", BUSY, 409),
        (
            "/phrases/7/regenerate-media", "regenerate_phrase_media_use_case",
            PhraseNotFoundError(7), 404,
        ),
    ])
    def test_is_refused(
        self, client: TestClient, path: str, use_case: str, error: Exception, status: int,
    ) -> None:
        getattr(_get_mock_container(), use_case).return_value.execute.side_effect = error

        assert client.post(path).status_code == status

    def test_meaning_is_queued_for_the_phrase(self, client: TestClient) -> None:
        use_case = _get_mock_container().enqueue_phrase_meaning_use_case.return_value

        response = client.post("/phrases/7/generate-meaning")

        assert response.status_code == 202
        use_case.execute.assert_called_once_with(7, None)

    def test_a_follow_up_is_queued_with_its_question(self, client: TestClient) -> None:
        use_case = _get_mock_container().enqueue_phrase_meaning_use_case.return_value

        response = client.post(
            "/phrases/7/generate-meaning", json={"action": "free_question", "text": "Why?"},
        )

        assert response.status_code == 202
        use_case.execute.assert_called_once_with(7, MeaningFollowUp("free_question", "Why?"))

    def test_meaning_of_a_busy_source_is_refused(self, client: TestClient) -> None:
        use_case = _get_mock_container().enqueue_phrase_meaning_use_case.return_value
        use_case.execute.side_effect = BUSY

        assert client.post("/phrases/7/generate-meaning").status_code == 409

    def test_the_old_card_paths_are_gone(self, client: TestClient) -> None:
        for path in (
            "/candidates/1/generate-tts", "/candidates/1/polish",
            "/candidates/1/regenerate-media", "/candidates/1/generate-meaning",
        ):
            assert client.post(path).status_code in (404, 405), path


@pytest.mark.unit
def test_generation_of_a_busy_source_is_refused(client: TestClient) -> None:
    use_case = _get_mock_container().run_generation_use_case.return_value
    use_case.execute.side_effect = BUSY

    response = client.post(
        "/api/review/generation/meaning", params={"scope": "source-1", "cards": "missing"},
    )

    assert response.status_code == 409


@pytest.mark.unit
def test_topic_generation_of_a_busy_topic_is_refused(client: TestClient) -> None:
    use_case = _get_mock_container().enqueue_topic_generation_use_case.return_value
    use_case.execute.side_effect = SourceOperationBusyError(1, "refresh")

    assert client.post("/sources/1/topic-targets/generate").status_code == 409
