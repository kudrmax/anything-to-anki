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
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["cefr_level"] == "B1"
        assert data["anki_deck_name"] == "Default"
        assert data["ai_provider"] == "claude"
        assert data["ai_model"] == "sonnet"
        assert data["anki_note_type"] == "AnythingToAnkiType"
        assert data["anki_field_sentence"] == "Sentence"
        assert data["anki_field_target_word"] == "Target"
        assert data["anki_field_meaning"] == "Meaning"
        assert data["anki_field_ipa"] == "IPA"
        assert data["anki_field_image"] == "Image"
        assert data["anki_field_audio"] == "Audio"
        assert data["anki_field_translation"] == "Translation"
        assert data["anki_field_synonyms"] == "Synonyms"

    def test_update_translation_synonyms_fields(self, client: TestClient) -> None:
        response = client.patch(
            "/api/settings",
            json={"anki_field_translation": "RU", "anki_field_synonyms": "Syn"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["anki_field_translation"] == "RU"
        assert data["anki_field_synonyms"] == "Syn"
        response = client.get("/api/settings")
        data = response.json()
        assert data["anki_field_translation"] == "RU"
        assert data["anki_field_synonyms"] == "Syn"

    def test_update_image_audio_fields(self, client: TestClient) -> None:
        response = client.patch(
            "/api/settings",
            json={"anki_field_image": "Picture", "anki_field_audio": "Sound"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["anki_field_image"] == "Picture"
        assert data["anki_field_audio"] == "Sound"
        # Verify persistence on subsequent GET
        response = client.get("/api/settings")
        data = response.json()
        assert data["anki_field_image"] == "Picture"
        assert data["anki_field_audio"] == "Sound"

    def test_update_cefr_level(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"cefr_level": "C1"})
        assert response.status_code == 200
        assert response.json()["cefr_level"] == "C1"
        response = client.get("/api/settings")
        assert response.json()["cefr_level"] == "C1"

    def test_update_deck_name(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"anki_deck_name": "MyDeck"})
        assert response.status_code == 200
        assert response.json()["anki_deck_name"] == "MyDeck"

    def test_update_both(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"cefr_level": "C2", "anki_deck_name": "Learning"})
        assert response.status_code == 200
        data = response.json()
        assert data["cefr_level"] == "C2"
        assert data["anki_deck_name"] == "Learning"

    def test_update_invalid_level(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"cefr_level": "X9"})
        assert response.status_code == 422

    def test_update_no_fields_returns_422(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={})
        assert response.status_code == 422
