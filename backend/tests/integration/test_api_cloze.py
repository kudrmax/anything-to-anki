from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from typing import Any

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import AnkiSyncedCardModel, SourceModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

GIVE_UP = "She finally gave up smoking last year."
SOURCE_ID = 1
CANDIDATE_ID = 1
SYNCED_CANDIDATE_ID = 2


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    session = session_factory()
    source = SourceModel(raw_text=GIVE_UP, status="done", cleaned_text=GIVE_UP)
    session.add(source)
    session.flush()
    SqlaCandidateRepository(session).create_batch([
        StoredCandidate(
            source_id=source.id, lemma=lemma, pos="VERB", cefr_level="B1",
            zipf_frequency=4.0, context_fragment=GIVE_UP, fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING, surface_form=surface,
            is_phrasal_verb=" " in lemma,
        )
        for lemma, surface in [("give up", "gave up"), ("smoke", "smoking")]
    ])
    session.add(AnkiSyncedCardModel(candidate_id=SYNCED_CANDIDATE_ID, anki_note_id=777))
    session.commit()
    session.close()

    def override_session() -> Generator[Session, None, None]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _candidate_in_source(client: TestClient, candidate_id: int) -> dict[str, Any]:
    response = client.get(f"/sources/{SOURCE_ID}")
    assert response.status_code == 200
    candidates: list[dict[str, Any]] = response.json()["candidates"]
    return next(c for c in candidates if c["id"] == candidate_id)


@pytest.mark.integration
class TestSaveClozeAPI:
    def test_save_marks_learn_and_shows_cloze(self, client: TestClient) -> None:
        response = client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={
                "hidden_word_indices": [3, 2], "hint_kind": "first_letter", "phrase": GIVE_UP,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "learn"
        assert body["cloze"] == {
            "hidden_word_indices": [2, 3], "hint_kind": "first_letter", "custom_hint": None,
        }
        assert body["can_cloze"] is True

        candidate = _candidate_in_source(client, CANDIDATE_ID)
        assert candidate["status"] == "learn"
        assert candidate["cloze"]["hidden_word_indices"] == [2, 3]

    def test_synced_candidate_cannot_be_clozed(self, client: TestClient) -> None:
        assert _candidate_in_source(client, SYNCED_CANDIDATE_ID)["can_cloze"] is False
        response = client.put(
            f"/candidates/{SYNCED_CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [4], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 409

    def test_empty_indices_are_rejected(self, client: TestClient) -> None:
        response = client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 422

    def test_unknown_hint_kind_is_rejected(self, client: TestClient) -> None:
        response = client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "bogus", "phrase": GIVE_UP},
        )
        assert response.status_code == 422

    def test_missing_candidate_is_404(self, client: TestClient) -> None:
        response = client.put(
            "/candidates/999/cloze",
            json={"hidden_word_indices": [0], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 404

    def test_status_change_drops_cloze(self, client: TestClient) -> None:
        client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [2, 3], "hint_kind": "none", "phrase": GIVE_UP},
        )
        response = client.patch(f"/candidates/{CANDIDATE_ID}", json={"status": "skip"})
        assert response.status_code == 200
        response = client.patch(f"/candidates/{CANDIDATE_ID}", json={"status": "learn"})
        assert response.status_code == 200
        assert _candidate_in_source(client, CANDIDATE_ID)["cloze"] is None

    def test_markup_of_another_phrase_is_rejected(self, client: TestClient) -> None:
        response = client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "none", "phrase": "Old phrase."},
        )
        assert response.status_code == 409
        assert _candidate_in_source(client, CANDIDATE_ID)["status"] == "pending"

    def test_missing_phrase_is_rejected(self, client: TestClient) -> None:
        response = client.put(
            f"/candidates/{CANDIDATE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "none"},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestPreviewClozeAPI:
    def test_preview_defaults_to_target(self, client: TestClient) -> None:
        response = client.post(f"/candidates/{CANDIDATE_ID}/cloze/preview", json={})
        assert response.status_code == 200
        body = response.json()
        assert [w["text"] for w in body["words"]][:4] == ["She", "finally", "gave", "up"]
        assert body["hidden_word_indices"] == [2, 3]
        assert body["front"] == "She finally […] smoking last year."
        assert body["hint_kind"] == "none"
        assert "first_letter" in body["available_hints"]
        assert body["phrase"] == GIVE_UP
        assert body["can_save"] is True

    def test_preview_uses_default_hint_setting(self, client: TestClient) -> None:
        settings = client.patch("/api/settings", json={"cloze_default_hint": "first_letter"})
        assert settings.status_code == 200
        response = client.post(f"/candidates/{CANDIDATE_ID}/cloze/preview", json={})
        assert response.json()["hint"] == "g… u…"

    def test_default_hint_setting_rejects_custom(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"cloze_default_hint": "custom"})
        assert response.status_code == 422

    def test_preview_rejects_out_of_range_indices(self, client: TestClient) -> None:
        response = client.post(
            f"/candidates/{CANDIDATE_ID}/cloze/preview", json={"hidden_word_indices": [42]},
        )
        assert response.status_code == 422

    def test_preview_missing_candidate_is_404(self, client: TestClient) -> None:
        response = client.post("/candidates/999/cloze/preview", json={})
        assert response.status_code == 404
