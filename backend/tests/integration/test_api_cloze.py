from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from typing import Any

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tests.phrase_support import phrase
from tests.projection_support import rebuild_projection
from tests.review_support import card_in, on_review
from tests.review_window_support import review_list
from tests.word_support import PHRASE_ID_OFFSET, CardSeed, bind, store_cards

GIVE_UP = "She finally gave up smoking last year."
SOURCE_ID = 1
PHRASE_ID = PHRASE_ID_OFFSET + 1
SYNCED_WORD_ID = 2
SYNCED_PHRASE_ID = PHRASE_ID_OFFSET + 2


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
    source = SourceModel(title=GIVE_UP, status="done")
    session.add(source)
    session.flush()
    store_cards(session, [
        CardSeed(
            StoredCandidate(
                source_id=source.id,
                lemma=lemma,
                pos="VERB",
                cefr_level="B1",
                zipf_frequency=4.0,
                occurrences=1,
                status=WordStatus.NEW,
                is_phrasal_verb=" " in lemma,
            ),
            phrase(GIVE_UP, lemma, lemmas={"gave": "give", "smoking": "smoke"}),
        )
        for lemma in ["give up", "smoke"]
    ])
    session.execute(
        text("UPDATE phrases SET choice = 'cloze' WHERE id = :id"), {"id": SYNCED_PHRASE_ID},
    )
    bind(session, SYNCED_WORD_ID, SYNCED_PHRASE_ID, note_id=777, kind="cloze")
    session.commit()
    rebuild_projection(session)
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


def _candidate_in_source(client: TestClient, phrase_id: int) -> dict[str, Any]:
    candidates = review_list(client, f"source-{SOURCE_ID}")
    return next(c for c in candidates if c["phrase_id"] == phrase_id)


@pytest.mark.integration
class TestSaveClozeAPI:
    def test_save_marks_learn_and_shows_cloze(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={
                "hidden_word_indices": [3, 2], "hint_kind": "first_letter", "phrase": GIVE_UP,
            },
        )
        assert response.status_code == 200
        body = card_in(response.json(), PHRASE_ID)
        assert (body["choice"], body["shown"]["status"]) == ("cloze", "learn")
        assert body["cloze"] == {
            "hidden_word_indices": [2, 3], "hint_kind": "first_letter", "custom_hint": None,
        }
        assert body["can_edit_cloze"] is True

        candidate = _candidate_in_source(client, PHRASE_ID)
        assert candidate["choice"] == "cloze"
        assert candidate["cloze"]["hidden_word_indices"] == [2, 3]

    def test_the_save_that_makes_a_cloze_offers_its_undo_and_an_edit_none(
        self, client: TestClient,
    ) -> None:
        def save() -> dict[str, object] | None:
            response = on_review(
                client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
                json={"hidden_word_indices": [3], "hint_kind": "none", "phrase": GIVE_UP},
            )
            undo: dict[str, object] | None = response.json()["undo"]
            return undo

        assert save() == {"phrase_id": PHRASE_ID, "button": "cloze"}
        assert save() is None

    def test_a_cloze_in_anki_keeps_its_markup(self, client: TestClient) -> None:
        assert _candidate_in_source(client, SYNCED_PHRASE_ID)["can_edit_cloze"] is False
        response = on_review(
            client, "PUT", f"/phrases/{SYNCED_PHRASE_ID}/cloze",
            json={"hidden_word_indices": [4], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 409

    def test_empty_indices_are_rejected(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={"hidden_word_indices": [], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 422

    def test_unknown_hint_kind_is_rejected(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "bogus", "phrase": GIVE_UP},
        )
        assert response.status_code == 422

    def test_missing_candidate_is_404(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", "/phrases/999/cloze",
            json={"hidden_word_indices": [0], "hint_kind": "none", "phrase": GIVE_UP},
        )
        assert response.status_code == 404

    def test_a_card_no_longer_a_cloze_shows_no_markup(self, client: TestClient) -> None:
        on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={"hidden_word_indices": [2, 3], "hint_kind": "none", "phrase": GIVE_UP},
        )
        response = on_review(
            client, "POST", f"/phrases/{PHRASE_ID}/decision", json={"button": "skip"},
        )
        assert response.status_code == 200
        response = on_review(
            client, "POST", f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"},
        )
        assert response.status_code == 200
        assert _candidate_in_source(client, PHRASE_ID)["cloze"] is None

    def test_markup_of_another_phrase_is_rejected(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "none", "phrase": "Old phrase."},
        )
        assert response.status_code == 409
        assert _candidate_in_source(client, PHRASE_ID)["choice"] == "none"

    def test_missing_phrase_is_rejected(self, client: TestClient) -> None:
        response = on_review(
            client, "PUT", f"/phrases/{PHRASE_ID}/cloze",
            json={"hidden_word_indices": [2], "hint_kind": "none"},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestPreviewClozeAPI:
    def test_preview_defaults_to_target(self, client: TestClient) -> None:
        response = client.post(f"/phrases/{PHRASE_ID}/cloze/preview", json={})
        assert response.status_code == 200
        body = response.json()
        assert [w["text"] for w in body["words"]][:4] == ["She", "finally", "gave", "up"]
        assert body["hidden_word_indices"] == [2, 3]
        assert body["front"] == [
            {"text": "She finally ", "is_gap": False},
            {"text": "[…]", "is_gap": True},
            {"text": " smoking last year.", "is_gap": False},
        ]
        assert body["hint_kind"] == "none"
        assert "first_letter" in body["available_hints"]
        assert body["phrase"] == GIVE_UP
        assert body["can_save"] is True

    def test_preview_uses_default_hint_setting(self, client: TestClient) -> None:
        settings = client.patch("/api/settings", json={"cloze_default_hint": "first_letter"})
        assert settings.status_code == 200
        response = client.post(f"/phrases/{PHRASE_ID}/cloze/preview", json={})
        assert {"text": "[g… u…]", "is_gap": True} in response.json()["front"]

    def test_default_hint_setting_rejects_custom(self, client: TestClient) -> None:
        response = client.patch("/api/settings", json={"cloze_default_hint": "custom"})
        assert response.status_code == 422

    def test_preview_rejects_out_of_range_indices(self, client: TestClient) -> None:
        response = client.post(
            f"/phrases/{PHRASE_ID}/cloze/preview", json={"hidden_word_indices": [42]},
        )
        assert response.status_code == 422

    def test_preview_missing_candidate_is_404(self, client: TestClient) -> None:
        response = client.post("/phrases/999/cloze/preview", json={})
        assert response.status_code == 404
