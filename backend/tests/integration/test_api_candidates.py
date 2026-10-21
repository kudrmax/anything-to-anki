from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_word_mark_repository import (
    SqlaWordMarkRepository,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.projection_support import rebuild_projection
from tests.word_support import (
    DECISION_STATUSES_SQL,
    PHRASE_ID_OFFSET,
    CardSeed,
    bind,
    insert_word,
    phrase_id_of,
    store_cards,
)

WORD_ID = 1
PHRASE_ID = PHRASE_ID_OFFSET + 1
OTHER_SOURCE = 2
OTHER_WORD = 50


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
    text = "It was always the pursuit of happiness, he said."
    source = SourceModel(title="Test", status="done")
    session.add(source)
    session.flush()
    SqlaDocumentRepository(session).save(
        source.id, Document((Paragraph(lines=(Line(text),), mode=ParagraphMode.FLOW),)),
    )
    phrase_start = text.index("the pursuit of")
    store_cards(session, [
        CardSeed(
            StoredCandidate(
                source_id=source.id,
                lemma="pursuit",
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=3.5,
                occurrences=1,
                status=WordStatus.NEW,
            ),
            phrase("the pursuit of", "pursuit"),
            position=DocumentPosition(0, 0, phrase_start, 0, phrase_start + 14),
        ),
    ])
    session.commit()
    rebuild_projection(session)
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
class TestDecisionAPI:
    def test_mark_candidate_learn(self, client: TestClient) -> None:
        response = client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})
        assert response.status_code == 200
        assert response.json()["choice"] == "learn"

    def test_mark_candidate_known(self, client: TestClient) -> None:
        response = client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "known"})
        assert response.status_code == 200
        # Verify it was added to known words
        kw_response = client.get("/known-words")
        assert any(w["lemma"] == "pursuit" for w in kw_response.json())

    def test_marking_the_last_pending_candidate_marks_the_source_reviewed(
        self, client: TestClient,
    ) -> None:
        assert client.get("/api/review", params={"scope": "source-1"}).json()["status"] == "done"
        client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})
        review = client.get("/api/review", params={"scope": "source-1"}).json()
        assert review["status"] == "reviewed"

    def test_undo_returns_the_candidate_and_the_source_to_review(
        self, client: TestClient,
    ) -> None:
        client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})
        response = client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})
        assert response.status_code == 200
        # Nothing decided again: the source reads as not started, as its progress says.
        assert client.get("/api/review", params={"scope": "source-1"}).json()["status"] == "done"

    def test_undoing_known_removes_the_word_from_known_words(
        self, client: TestClient,
    ) -> None:
        client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "known"})
        client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "known"})
        assert all(w["lemma"] != "pursuit" for w in client.get("/known-words").json())

    def test_mark_candidate_not_found(self, client: TestClient) -> None:
        response = client.post("/phrases/999/decision", json={"button": "learn"})
        assert response.status_code == 404

    def test_a_decision_on_a_sibling_card_is_refused(self, client: TestClient) -> None:
        session = next(app.dependency_overrides[get_db_session]())
        sibling = SqlaOccurrenceRepository(session, SessionChangeRecorder(session)).add(Occurrence(
            candidate_id=WORD_ID, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase("the pursuit of", "pursuit"), phrase_position=None,
            key=None, fragment_score=None,
            earned_section=CandidateSection.READY, shown_by=ShownBy.USER,
        ))
        session.commit()
        client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})

        response = client.post(f"/phrases/{sibling.id}/decision", json={"button": "known"})

        assert response.status_code == 409
        assert response.json()["detail"] == "Learned via another phrase: change it on that card"

    def test_learn_on_a_word_known_elsewhere_says_why(self, client: TestClient) -> None:
        session = next(app.dependency_overrides[get_db_session]())
        marks = SqlaWordMarkRepository(session, SessionChangeRecorder(session))
        marks.mark_known("pursuit", "NOUN")
        session.commit()

        response = client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "learn"})

        assert response.status_code == 409
        assert response.json()["detail"] == "Already known"

    def test_mark_candidate_invalid_status(self, client: TestClient) -> None:
        response = client.post(f"/phrases/{PHRASE_ID}/decision", json={"button": "invalid"})
        assert response.status_code == 422


@pytest.mark.integration
class TestCardReportsAPI:
    def test_report_keeps_a_snapshot_of_the_card(self, client: TestClient) -> None:
        response = client.post(
            f"/phrases/{PHRASE_ID}/report",
            json={"reasons": ["Phrase too long"], "comment": " odd split "},
        )
        assert response.status_code == 201
        report = response.json()
        assert report["reasons"] == ["Phrase too long"]
        assert report["comment"] == "odd split"
        assert report["lemma"] == "pursuit"
        assert report["context_fragment"] == "the pursuit of"
        assert report["text_before"] == "It was always "
        assert report["text_after"] == " happiness, he said."

    def test_report_keeps_several_reasons(self, client: TestClient) -> None:
        reasons = ["Phrase too long", "Wrong word form"]
        response = client.post(f"/phrases/{PHRASE_ID}/report", json={"reasons": reasons})
        assert response.status_code == 201
        assert response.json()["reasons"] == reasons
        assert response.json()["comment"] == ""

    def test_reports_are_listed_newest_first(self, client: TestClient) -> None:
        client.post(f"/phrases/{PHRASE_ID}/report", json={"comment": "first"})
        client.post(f"/phrases/{PHRASE_ID}/report", json={"comment": "second"})
        comments = [r["comment"] for r in client.get("/api/card-reports").json()]
        assert comments == ["second", "first"]

    def test_report_outlives_the_source(self, client: TestClient) -> None:
        client.post(f"/phrases/{PHRASE_ID}/report", json={"reasons": ["Wrong phrase boundary"]})
        client.delete("/sources/1")
        assert len(client.get("/api/card-reports").json()) == 1

    def test_report_without_reasons_or_comment_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            f"/phrases/{PHRASE_ID}/report", json={"reasons": [], "comment": "   "},
        )
        assert response.status_code == 422

    def test_unknown_reason_is_rejected(self, client: TestClient) -> None:
        response = client.post(f"/phrases/{PHRASE_ID}/report", json={"reasons": ["Made up"]})
        assert response.status_code == 422

    def test_unknown_candidate(self, client: TestClient) -> None:
        assert client.post("/phrases/999/report", json={"comment": "x"}).status_code == 404

    def test_reported_candidate_is_marked(self, client: TestClient) -> None:
        def reported() -> bool:
            candidates = client.get("/api/review/candidates", params={"scope": "source-1"}).json()
            return next(c for c in candidates if c["phrase_id"] == PHRASE_ID)["reported"]

        assert reported() is False
        client.post(f"/phrases/{PHRASE_ID}/report", json={"comment": "x"})
        assert reported() is True

    def test_marking_a_word_unknown_makes_its_known_cards_new_everywhere(
        self, client: TestClient,
    ) -> None:
        """§2.7 (a): the Unknown of a report removes Known as any removal does."""
        session = next(app.dependency_overrides[get_db_session]())
        insert_source(session, OTHER_SOURCE)
        insert_word(session, OTHER_WORD, source_id=OTHER_SOURCE, lemma="pursuit", status="known")
        bind(session, OTHER_WORD, phrase_id_of(OTHER_WORD))
        marks = SqlaWordMarkRepository(session, SessionChangeRecorder(session))
        marks.mark_known("pursuit", "NOUN")
        session.commit()

        response = client.post(
            f"/phrases/{PHRASE_ID}/report",
            json={"reasons": ["More than one unknown word"], "unknown_words": [1]},
        )

        assert response.status_code == 201
        session = next(app.dependency_overrides[get_db_session]())
        rows = session.execute(text(
            "SELECT s.status, p.choice, a.released_at IS NOT NULL"
            f" FROM ({DECISION_STATUSES_SQL}) s"  # noqa: S608
            " JOIN phrases p ON p.candidate_id = s.word_id"
            " JOIN anki_synced_cards a ON a.phrase_id = p.id WHERE s.word_id = :id"
        ), {"id": OTHER_WORD}).all()
        assert [tuple(row) for row in rows] == [("pending", "none", 1)]
        assert all(w["lemma"] != "pursuit" for w in client.get("/known-words").json())

    def test_reasons(self, client: TestClient) -> None:
        reasons = client.get("/api/card-reports/reasons").json()
        assert {"label": "Wrong phrase boundary", "picks_words": False} in reasons
        assert [r["label"] for r in reasons if r["picks_words"]] == ["More than one unknown word"]


@pytest.mark.integration
class TestTargetImageAPI:
    def test_refuses_to_download_a_url_no_source_handed_out(self, client: TestClient) -> None:
        response = client.put("/words/1/image", json={"url": "https://evil.example/x.jpg"})

        assert response.status_code == 400

    def test_unknown_candidate(self, client: TestClient) -> None:
        response = client.get("/words/999/image-options")

        assert response.status_code == 404

    def test_pasting_for_an_unknown_candidate(self, client: TestClient) -> None:
        response = client.put(
            "/words/999/image/pasted",
            content=b"picture",
            headers={"Content-Type": "image/png"},
        )

        assert response.status_code == 404


@pytest.mark.integration
class TestUnknownWordsAPI:
    """Words of a phrase the user doesn't know take the card out of Ready."""

    def _card(self, client: TestClient) -> dict[str, object]:
        source = client.get("/api/review", params={"scope": "source-1"}).json()
        section = source["candidates"][0]["section"]
        return {"section": section, "ready": source["progress"]["total"]}

    def test_card_is_ready_at_first(self, client: TestClient) -> None:
        assert self._card(client) == {"section": "ready", "ready": 1}

    def test_word_marked_in_a_report_moves_the_card_to_extra(self, client: TestClient) -> None:
        response = client.post(
            f"/phrases/{PHRASE_ID}/report",
            json={
                "reasons": ["More than one unknown word"],
                "unknown_words": [0],
            },
        )
        assert response.status_code == 201
        assert [w["lemma"] for w in client.get("/unknown-words").json()] == ["the"]
        assert self._card(client) == {"section": "extra", "ready": 0}

    def test_removing_the_unknown_word_returns_the_card_to_ready(
        self, client: TestClient,
    ) -> None:
        client.post(f"/phrases/{PHRASE_ID}/report", json={"unknown_words": [0]})
        word = client.get("/unknown-words").json()[0]
        assert client.delete(f"/unknown-words/{word['id']}").status_code == 200
        assert self._card(client) == {"section": "ready", "ready": 1}

    def test_source_with_no_ready_cards_left_is_reviewed(self, client: TestClient) -> None:
        client.post(f"/phrases/{PHRASE_ID}/report", json={"unknown_words": [0]})
        review = client.get("/api/review", params={"scope": "source-1"}).json()
        assert review["status"] == "reviewed"

    def test_new_phrase_is_read_again(self, client: TestClient) -> None:
        client.put(f"/phrases/{PHRASE_ID}/phrase", json={"phrase": "the ominous pursuit of"})
        assert self._card(client) == {"section": "extra", "ready": 0}
        client.put(f"/phrases/{PHRASE_ID}/phrase", json={"phrase": "the long pursuit of"})
        assert self._card(client) == {"section": "ready", "ready": 1}
