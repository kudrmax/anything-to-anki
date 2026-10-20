from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest
from backend.application.utils.anki_note_settings import AnkiFieldNames
from backend.application.utils.export_queue import ExportBatch
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tests.export_support import export_card
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from collections.abc import Generator

    from backend.application.utils.export_queue import ExportCard
    from httpx import Response


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


@pytest.fixture()
def db_session(client: TestClient) -> Generator[Session, None, None]:
    """Direct session for seeding test data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _no_real_anki() -> Generator[None, None, None]:
    """Whatever a test does not stub finds Anki offline: no request leaves the machine."""
    with patch(
        "backend.infrastructure.adapters.anki_connect_connector.httpx.post",
        side_effect=httpx.ConnectError("Anki is not running in tests"),
    ):
        yield


_DEFAULT_CLOZE_FIELDS = AnkiFieldNames.read(MagicMock(**{"get.return_value": None})).cloze_fields()
_CONNECTOR = "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector"


@pytest.mark.integration
class TestNoteTypesAPI:
    def test_returns_503_when_anki_unavailable(self, client: TestClient) -> None:
        with patch(f"{_CONNECTOR}.is_available", return_value=False):
            assert client.get("/anki/note-types").status_code == 503
            assert client.post("/anki/note-types/cloze/fix").status_code == 503

    def test_checks_both_note_types_of_the_saved_settings(self, client: TestClient) -> None:
        assert client.patch("/api/settings", json={"anki_note_type": "Main"}).status_code == 200
        fields = {"Main": ["Sentence", "Target"], "AnythingToAnkiCloze": None}
        with (
            patch(f"{_CONNECTOR}.is_available", return_value=True),
            patch(f"{_CONNECTOR}.get_model_field_names", side_effect=fields.get),
        ):
            response = client.get("/anki/note-types")

        assert response.status_code == 200
        main, cloze = response.json()
        assert (main["kind"], main["note_type"]) == ("recognition", "Main")
        assert main["fix"] == "add_fields"
        assert "MeaningImage" in main["missing_fields"]
        assert (cloze["kind"], cloze["fix"]) == ("cloze", "create")

    def test_fixes_only_the_requested_type(self, client: TestClient) -> None:
        with (
            patch(f"{_CONNECTOR}.is_available", return_value=True),
            patch(f"{_CONNECTOR}.get_model_field_names", return_value=None),
            patch(f"{_CONNECTOR}.ensure_note_type") as ensure,
        ):
            response = client.post("/anki/note-types/cloze/fix")

        assert response.status_code == 200
        assert [c.args[0] for c in ensure.call_args_list] == ["AnythingToAnkiCloze"]
        assert ensure.call_args.kwargs["front_template"]

    def test_unknown_kind(self, client: TestClient) -> None:
        assert client.post("/anki/note-types/basic/fix").status_code == 422


@pytest.mark.integration
class TestAnkiStatusAPI:
    def test_status_when_unavailable(self, client: TestClient) -> None:
        with patch(
            "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.is_available",
            return_value=False,
        ):
            response = client.get("/anki/status")
        assert response.status_code == 200
        assert response.json()["available"] is False

    def test_status_when_available(self, client: TestClient) -> None:
        with patch(
            "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.is_available",
            return_value=True,
        ):
            response = client.get("/anki/status")
        assert response.status_code == 200
        assert response.json()["available"] is True


@pytest.mark.integration
class TestGetExportCardsAPI:
    def test_returns_cards_for_source(self, client: TestClient) -> None:
        # Seed via API
        post = _add_text(client, "burnout is common")
        source_id = post.json()["source_ids"][0]

        response = client.get(f"/export/cards?scope=source-{source_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["ready"], list)
        assert isinstance(data["incomplete"], list)
        assert data["title"] == client.get("/sources").json()[0]["title"]

    def test_returns_all_export_cards(self, client: TestClient) -> None:
        _add_text(client, "burnout is common")

        response = client.get("/export/cards")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["ready"], list)
        assert isinstance(data["incomplete"], list)
        assert data["title"] == "All sources"

    def test_rejects_an_unknown_scope(self, client: TestClient) -> None:
        assert client.get("/export/cards?scope=nonsense").status_code == 400
        assert client.post("/export/sync-to-anki?group=ready&scope=nonsense").status_code == 400

    def test_missing_collection_is_not_found(self, client: TestClient) -> None:
        assert client.get("/export/cards?scope=9999").status_code == 404
        assert client.post("/export/sync-to-anki?group=ready&scope=9999").status_code == 404

    def test_missing_source_is_not_found(self, client: TestClient) -> None:
        assert client.get("/export/cards?scope=source-9999").status_code == 404
        assert client.post("/export/sync-to-anki?group=ready&scope=source-9999").status_code == 404

    def test_per_source_paths_are_gone(self, client: TestClient) -> None:
        post = _add_text(client, "burnout is common")
        source_id = post.json()["source_ids"][0]
        assert client.get(f"/export/cards/{source_id}").status_code == 404
        assert client.post(f"/export/sync-to-anki/{source_id}?group=ready").status_code == 404


@pytest.mark.integration
class TestSyncToAnkiAPI:
    def test_returns_503_when_anki_unavailable(self, client: TestClient) -> None:
        post = _add_text(client, "some text here for testing")
        source_id = post.json()["source_ids"][0]

        with patch(
            "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.is_available",
            return_value=False,
        ):
            # Need at least one learn candidate - with empty source there are none,
            # so total=0 and returns 200
            response = client.post(
                f"/export/sync-to-anki?group=incomplete&scope=source-{source_id}",
            )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_returns_zero_for_source_with_no_learn_candidates(self, client: TestClient) -> None:
        post = _add_text(client, "test text")
        source_id = post.json()["source_ids"][0]

        response = client.post(f"/export/sync-to-anki?group=incomplete&scope=source-{source_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["added"] == 0
        assert "matured" not in data

    def test_sync_adds_cards_successfully(self, client: TestClient) -> None:
        post = _add_text(client, "burnout is exhausting")
        source_id = post.json()["source_ids"][0]
        burnout = _burnout(source_id)

        # Mark first candidate as learn via mock on candidate repo
        with (
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.is_available",
                return_value=True,
            ),
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.ensure_note_type",
            ),
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.get_model_field_names",
                return_value=_DEFAULT_CLOZE_FIELDS,
            ),
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.ensure_deck",
            ),
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.find_notes_by_target",
                return_value=[],
            ),
            patch(
                "backend.infrastructure.adapters.anki_connect_connector.AnkiConnectConnector.add_notes",
                return_value=[12345],
            ),
            patch(
                "backend.application.utils.export_queue.ExportQueue.for_sources",
                return_value=ExportBatch(pending=[burnout], exported_count=0),
            ),
            patch(
                "backend.application.utils.decision_effects.DecisionEffects.apply",
            ) as bound,
        ):
            response = client.post(
                f"/export/sync-to-anki?group=incomplete&scope=source-{source_id}",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["added"] == 1
        assert data["skipped"] == 0
        [call] = bound.call_args_list
        assert call.kwargs["note_id"] == 12345
        assert call.args[1].row == "S1"

    def test_requires_export_group(self, client: TestClient) -> None:
        post = _add_text(client, "test text")
        source_id = post.json()["source_ids"][0]

        assert client.post(f"/export/sync-to-anki?scope=source-{source_id}").status_code == 422
        assert client.post("/export/sync-to-anki").status_code == 422

    def test_ready_group_leaves_incomplete_cards_out(self, client: TestClient) -> None:
        post = _add_text(client, "burnout is exhausting")
        source_id = post.json()["source_ids"][0]

        with patch(
            "backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository.get_by_source",
            return_value=[_burnout(source_id).word],
        ):
            response = client.post(f"/export/sync-to-anki?group=ready&scope=source-{source_id}")

        assert response.status_code == 200
        assert response.json()["total"] == 0


def _burnout(source_id: int) -> ExportCard:
    return export_card(
        StoredCandidate(
            id=1, source_id=source_id, lemma="burnout", pos="NOUN", cefr_level="B2",
            zipf_frequency=3.5, occurrences=1, status=WordStatus.LEARN,
        ),
        phrase("burnout is exhausting", "burnout"),
    )


def _add_text(client: TestClient, text: str) -> Response:
    return client.post("/sources/add", json={"text": text, "answers": {"text.kind": "text"}})


@pytest.mark.integration
class TestLearningAPI:
    def test_the_learning_list_is_read_only_and_split(self, client: TestClient) -> None:
        response = client.get("/vocabulary/learning")
        assert response.status_code == 200
        assert response.json() == {"in_anki": [], "awaiting_export": []}
