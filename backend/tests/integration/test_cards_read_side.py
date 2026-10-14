"""The read side through the API: a card is a shown phrase of a word."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.models import SourceModel
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from tests.phrase_support import phrase
from tests.word_support import insert_word

pytestmark = pytest.mark.integration

SOURCE = 1
GLARE, SPARK = 1, 2
TEXT = "He glared at me. She glared back. A spark flew."
SORTS = ("relevance", "key_words", "chronological")


def _at(fragment: str) -> DocumentPosition:
    start = TEXT.index(fragment)
    return DocumentPosition(0, 0, start, 0, start + len(fragment))


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with factory() as session:
        yield session


@pytest.fixture()
def client(factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class Bench:
    """Source 1: `glare` with two shown phrases and `spark` with a shown and a hidden one."""

    def __init__(self, session: Session) -> None:
        self.session = session
        session.add(SourceModel(id=SOURCE, title="Glares", status=SourceStatus.DONE.value))
        session.flush()
        SqlaDocumentRepository(session).save(
            SOURCE, Document((Paragraph(lines=(Line(TEXT),), mode=ParagraphMode.FLOW),)),
        )
        insert_word(session, GLARE, lemma="glare", phrase_text="He glared at me.")
        insert_word(session, SPARK, lemma="spark", phrase_text="A spark flew.")
        self.occurrences = SqlaOccurrenceRepository(session)
        self.occurrences.write_text(
            GLARE, phrase("He glared at me.", "glared"), _at("He glared at me."),
        )
        self.occurrences.write_text(SPARK, phrase("A spark flew.", "spark"), _at("A spark flew."))
        self.second_glare = self.add(GLARE, "She glared back.", "glared", ShownBy.USER)
        self.hidden_spark = self.add(SPARK, "A spark flew.", "spark", None)
        session.commit()

    def add(
        self, word_id: int, text: str, target: str, shown_by: ShownBy | None,
        *, origin: OccurrenceOrigin = OccurrenceOrigin.MANUAL,
        collected_from: PhraseOrigin | None = None,
    ) -> int:
        added = self.occurrences.add(Occurrence(
            candidate_id=word_id, origin=origin, source_phrase=phrase(text, target),
            phrase_position=_at(text) if text in TEXT else None, key=None,
            fragment_score=None, shown_by=shown_by, collected_from=collected_from,
        ))
        assert added.id is not None
        return added.id


@pytest.fixture()
def bench(session: Session) -> Bench:
    return Bench(session)


def _cards(client: TestClient, sort: str = "relevance") -> list[dict[str, object]]:
    response = client.get(f"/sources/{SOURCE}", params={"sort": sort})
    assert response.status_code == 200
    cards: list[dict[str, object]] = response.json()["candidates"]
    return cards


def _board(client: TestClient) -> list[dict[str, object]]:
    groups = client.get("/sources/board").json()["groups"]
    return [summary for group in groups for summary in group["sources"]]


def _card(client: TestClient, phrase_id: int) -> dict[str, object]:
    return next(c for c in _cards(client) if c["phrase_id"] == phrase_id)


class TestCardsArePhrases:
    def test_every_shown_phrase_is_a_card_keyed_by_its_phrase(
        self, client: TestClient, bench: Bench,
    ) -> None:
        cards = _cards(client)
        assert sorted(c["phrase_id"] for c in cards) == sorted([GLARE, bench.second_glare, SPARK])
        assert all("id" not in c for c in cards)
        assert {c["phrase_id"]: c["word_id"] for c in cards} == {
            GLARE: GLARE, bench.second_glare: GLARE, SPARK: SPARK,
        }

    def test_each_card_shows_its_own_phrase(self, client: TestClient, bench: Bench) -> None:
        assert _card(client, bench.second_glare)["phrase"]["text"] == "She glared back."  # type: ignore[index]
        assert _card(client, GLARE)["phrase"]["text"] == "He glared at me."  # type: ignore[index]

    @pytest.mark.parametrize("sort", SORTS)
    def test_cards_of_a_word_stand_together_in_every_order(
        self, client: TestClient, bench: Bench, session: Session, sort: str,
    ) -> None:
        bench.add(SPARK, "She glared back.", "glared", ShownBy.USER)
        session.commit()
        words = [c["word_id"] for c in _cards(client, sort)]
        assert words in ([GLARE, GLARE, SPARK, SPARK], [SPARK, SPARK, GLARE, GLARE])

    def test_get_candidates_lists_the_same_cards(self, client: TestClient, bench: Bench) -> None:
        listed = client.get(f"/sources/{SOURCE}/candidates").json()
        assert [c["phrase_id"] for c in listed] == [c["phrase_id"] for c in _cards(client)]


class TestDecisionsOnCards:
    def test_learn_on_one_card_decides_every_card_of_the_word(
        self, client: TestClient, bench: Bench,
    ) -> None:
        client.put(f"/phrases/{GLARE}/decision", json={"status": "learn"})
        source = client.get(f"/sources/{SOURCE}").json()
        assert source["progress"] == {"decided": 2, "total": 3}
        sibling = _card(client, bench.second_glare)
        assert sibling["word_status"] == "learn"
        assert sibling["status"] == "learn"
        assert sibling["is_decision"] is False

    def test_the_sibling_card_shows_the_decision_with_inactive_buttons(
        self, client: TestClient, bench: Bench,
    ) -> None:
        client.put(f"/phrases/{GLARE}/decision", json={"status": "learn"})
        here = _card(client, GLARE)
        sibling = _card(client, bench.second_glare)
        assert here["state"] == {
            "decided_here": True, "decided_elsewhere": None, "elsewhere": None,
            "buttons_enabled": ["cloze", "known", "learn", "skip", "undo"],
        }
        assert sibling["state"] == {
            "decided_here": False, "decided_elsewhere": "learn", "elsewhere": None,
            "buttons_enabled": [],
        }

    def test_skip_is_one_card_only(self, client: TestClient, bench: Bench) -> None:
        client.put(f"/phrases/{GLARE}/decision", json={"status": "skip"})
        assert _card(client, GLARE)["status"] == "skip"
        assert _card(client, GLARE)["phrase_skipped"] is True
        assert _card(client, bench.second_glare)["status"] == "pending"
        assert client.get(f"/sources/{SOURCE}").json()["progress"] == {"decided": 1, "total": 3}

    def test_a_word_known_elsewhere_is_done_and_out_of_ready(
        self, client: TestClient, bench: Bench, session: Session,
    ) -> None:
        SqlaKnownWordRepository(session).add("spark", None)
        session.commit()
        card = _card(client, SPARK)
        assert card["state"]["elsewhere"] == "known"  # type: ignore[index]
        assert card["state"]["buttons_enabled"] == ["known", "skip"]  # type: ignore[index]
        assert client.get(f"/sources/{SOURCE}").json()["progress"] == {"decided": 0, "total": 2}
        [summary] = _board(client)
        assert summary["progress"] == {"decided": 0, "total": 2}


class TestWhatEachCardCarries:
    def test_generation_status_comes_from_the_jobs_of_its_phrase(
        self, client: TestClient, bench: Bench, session: Session,
    ) -> None:
        SqlaJobRepository(session).enqueue([
            Job.queued(JobType.POLISH, SOURCE, GLARE, phrase_id=bench.second_glare,
                       phrase_revision=0),
            Job.queued(JobType.MEANING, SOURCE, GLARE, phrase_id=bench.second_glare,
                       phrase_revision=0),
        ])
        session.commit()
        assert _card(client, bench.second_glare)["polish_status"] == "queued"
        assert _card(client, bench.second_glare)["meaning"]["status"] == "queued"  # type: ignore[index]
        assert _card(client, GLARE)["polish_status"] is None
        assert _card(client, GLARE)["meaning"] is None

    def test_the_origin_label_comes_from_the_phrase(
        self, client: TestClient, bench: Bench, session: Session,
    ) -> None:
        generated = bench.add(
            SPARK, "Sparks fly upward.", "sparks", ShownBy.USER,
            origin=OccurrenceOrigin.COLLECTED, collected_from=PhraseOrigin.generated(),
        )
        real = bench.add(
            SPARK, "The spark of genius.", "spark", ShownBy.USER,
            origin=OccurrenceOrigin.COLLECTED, collected_from=PhraseOrigin.from_source("Book"),
        )
        session.commit()
        assert _card(client, generated)["origin"] == {"kind": "generated", "source_title": None}
        assert _card(client, real)["origin"] == {"kind": "source", "source_title": "Book"}
        assert _card(client, SPARK)["origin"] is None

    def test_a_report_marks_only_the_card_it_was_made_on(
        self, client: TestClient, bench: Bench,
    ) -> None:
        response = client.post(
            f"/phrases/{bench.second_glare}/report", json={"reasons": ["Phrase too long"]},
        )
        assert response.status_code == 201
        assert _card(client, bench.second_glare)["reported"] is True
        assert _card(client, GLARE)["reported"] is False


class TestPhraseLevelRoutes:
    def test_cloze_preview_is_of_the_phrase(self, client: TestClient, bench: Bench) -> None:
        response = client.post(f"/phrases/{bench.second_glare}/cloze/preview", json={})
        assert response.status_code == 200
        assert response.json()["phrase"] == "She glared back."
        assert client.post(f"/candidates/{GLARE}/cloze/preview", json={}).status_code in (404, 405)

    def test_editing_the_text_changes_only_that_card(
        self, client: TestClient, bench: Bench,
    ) -> None:
        response = client.put(
            f"/phrases/{bench.second_glare}/phrase", json={"phrase": "She glared."},
        )
        assert response.status_code == 200
        assert _card(client, bench.second_glare)["phrase"]["text"] == "She glared."  # type: ignore[index]
        assert _card(client, GLARE)["phrase"]["text"] == "He glared at me."  # type: ignore[index]

    def test_reverting_the_polish_switches_only_that_card(
        self, client: TestClient, bench: Bench,
    ) -> None:
        client.put(f"/phrases/{bench.second_glare}/phrase", json={"phrase": "She glared."})
        response = client.put(
            f"/phrases/{bench.second_glare}/polish/reverted", json={"reverted": True},
        )
        assert response.status_code == 200
        assert _card(client, bench.second_glare)["phrase"]["text"] == "She glared back."  # type: ignore[index]
        assert _card(client, bench.second_glare)["polish_reverted"] is True


class TestDocument:
    def test_marks_are_the_shown_phrases(self, client: TestClient, bench: Bench) -> None:
        highlights = client.get(f"/sources/{SOURCE}/document").json()["highlights"]
        assert sorted(h["phrase_id"] for h in highlights) == sorted(
            [GLARE, bench.second_glare, SPARK],
        )
        assert {h["phrase_id"]: h["word_id"] for h in highlights}[bench.second_glare] == GLARE


class TestBoard:
    def test_counts_are_of_cards_and_learn_words(
        self, client: TestClient, bench: Bench,
    ) -> None:
        client.put(f"/phrases/{GLARE}/decision", json={"status": "learn"})
        [summary] = _board(client)
        assert summary["candidate_count"] == 3
        assert summary["learn_count"] == 1
        assert summary["progress"] == {"decided": 2, "total": 3}

    def test_board_and_review_agree_on_progress(self, client: TestClient, bench: Bench) -> None:
        client.put(f"/phrases/{SPARK}/decision", json={"status": "skip"})
        [summary] = _board(client)
        assert summary["progress"] == client.get(f"/sources/{SOURCE}").json()["progress"]


class TestBusySource:
    def test_processing_shows_from_the_operation(
        self, client: TestClient, session: Session,
    ) -> None:
        session.add(SourceModel(id=SOURCE, title="New", status=SourceStatus.NEW.value))
        lock = SqlaSourceOperationLock(session)
        lock.acquire(SOURCE, SourceOperationKind.PROCESS)
        lock.set_stage(SOURCE, ProcessingStage.ANALYZING_TEXT)
        session.commit()
        [summary] = client.get("/sources").json()
        assert summary["status"] == "processing"
        assert summary["processing_stage"] == "analyzing_text"
        assert summary["busy_with"] == "process"
        detail = client.get(f"/sources/{SOURCE}").json()
        assert detail["status"] == "processing"
        assert detail["processing_stage"] == "analyzing_text"

    def test_a_source_being_rebuilt_keeps_its_status_and_offers_nothing(
        self, client: TestClient, bench: Bench, session: Session,
    ) -> None:
        SqlaSourceOperationLock(session).acquire(SOURCE, SourceOperationKind.REBUILD)
        session.commit()
        [summary] = client.get("/sources").json()
        assert summary["status"] == "done"
        assert summary["busy_with"] == "rebuild"
        assert summary["processing_stage"] is None
        assert summary["available_operation"] is None
        assert summary["operation_hint"]

    def test_a_free_source_offers_its_operation(self, client: TestClient, bench: Bench) -> None:
        [summary] = client.get("/sources").json()
        assert summary["busy_with"] is None
        assert summary["available_operation"] == "rebuild"
        assert summary["operation_hint"] is None

    def test_the_stored_status_has_no_processing(self) -> None:
        assert "PROCESSING" not in SourceStatus.__members__


class TestFromAnki:
    def test_a_word_known_by_maturity_is_marked_in_the_known_list(
        self, client: TestClient, session: Session,
    ) -> None:
        known = SqlaKnownWordRepository(session)
        known.add("glare", None, from_anki=True)
        known.add("spark", None)
        session.commit()
        listed = {w["lemma"]: w["from_anki"] for w in client.get("/known-words").json()}
        assert listed == {"glare": True, "spark": False}


class TestCleanupMedia:
    def test_clears_the_media_of_every_phrase_of_the_source(
        self, client: TestClient, bench: Bench, session: Session, tmp_path: object,
    ) -> None:
        from pathlib import Path
        root = Path(str(tmp_path))
        media = SqlaCandidateMediaRepository(session)
        for phrase_id in (GLARE, bench.second_glare):
            shot = root / f"p{phrase_id}_screenshot.webp"
            shot.write_bytes(b"x")
            media.upsert_for_phrase(phrase_id, CandidateMedia(
                candidate_id=GLARE, screenshot_path=str(shot), audio_path=None,
                start_ms=0, end_ms=1000, generated_at=datetime.now(tz=UTC),
            ))
        session.commit()
        response = client.post(
            "/api/settings/media-cleanup", json={"source_id": SOURCE, "kind": "images"},
        )
        assert response.status_code == 204
        assert list(root.iterdir()) == []
        session.expire_all()
        assert media.get_by_phrase_id(bench.second_glare).screenshot_path is None  # type: ignore[union-attr]
