from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def templates_dir(tmp_path: Path) -> Path:
    (tmp_path / "front.html").write_text("F:{{edit:%FIELD_SENTENCE%}}")
    (tmp_path / "back.html").write_text("B:{{edit:%FIELD_TARGET%}}")
    (tmp_path / "style.css").write_text(".card{}")
    return tmp_path


@pytest.fixture()
def client(templates_dir: Path) -> Generator[TestClient, None, None]:
    from backend.infrastructure.api.dependencies import get_container

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

    def override_container():
        mock_container = MagicMock()
        mock_renderer = AnkiTemplateRenderer(templates_dir)
        mock_container.anki_template_renderer.return_value = mock_renderer

        mock_settings_uc = MagicMock()
        mock_settings = MagicMock()
        mock_settings.anki_field_sentence = "Sentence"
        mock_settings.anki_field_target_word = "Target"
        mock_settings.anki_field_meaning = "Meaning"
        mock_settings.anki_field_ipa = "IPA"
        mock_settings.anki_field_image = "Image"
        mock_settings.anki_field_audio = "Audio"
        mock_settings.anki_field_translation = "Translation"
        mock_settings.anki_field_synonyms = "Synonyms"
        mock_settings.anki_field_examples = "Examples"
        mock_settings_uc.get_settings.return_value = mock_settings
        mock_container.manage_settings_use_case.return_value = mock_settings_uc

        return mock_container

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = override_session_factory
    app.dependency_overrides[get_container] = override_container
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestAnkiTemplatesAPI:
    def test_returns_rendered_templates(self, client: TestClient) -> None:
        response = client.get("/anki/templates")
        assert response.status_code == 200
        data = response.json()
        assert "front" in data
        assert "back" in data
        assert "css" in data
        assert "{{edit:Sentence}}" in data["front"]
        assert "{{edit:Target}}" in data["back"]
        assert "%FIELD_" not in data["front"]
        assert "%FIELD_" not in data["back"]
