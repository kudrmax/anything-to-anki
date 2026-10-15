from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine, Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

import pytest
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.api.routes import sources as sources_routes
from backend.infrastructure.api.source_operations import SourceOperationRegistry
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    PhraseModel,
    SourceModel,
    StoredCandidateModel,
    dump_phrase,
)
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tests.phrase_support import phrase
from tests.unit.infrastructure.epub.epub_builder import EpubBuilder, TocLink, page, prose


@pytest.fixture()
def _db_engine() -> Generator[object, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_db_engine: object) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=_db_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_db_engine: object) -> Generator[TestClient, None, None]:
    test_session_factory = sessionmaker(bind=_db_engine)

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


@pytest.fixture(autouse=True)
def _no_operations_of_other_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sources of every test get the same ids: operations of one must not show in another."""
    monkeypatch.setattr(sources_routes, "OPERATIONS", SourceOperationRegistry())


@pytest.fixture()
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Background operations started by the routes; none of them runs."""
    started: list[object] = []

    def record(work: Coroutine[object, object, None]) -> None:
        work.close()
        started.append(work)

    monkeypatch.setattr(sources_routes, "_in_background", record)
    return started


@pytest.fixture()
def launched(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Ids handed to the background launch; nothing is actually launched."""
    ids: list[int] = []

    def record(source_ids: list[int], *_: object) -> None:
        ids.extend(source_ids)

    monkeypatch.setattr(sources_routes, "_launch", record)
    return ids


TEXT_ANSWER = {"text.kind": "text"}
TEXT_REQUEST = {"text": "Hello world", "answers": TEXT_ANSWER}


@pytest.mark.integration
class TestSourcesAPI:
    def test_pasted_text_asks_text_or_song_first(self, client: TestClient) -> None:
        response = client.post("/sources/add", json={"text": "Hello world"})
        assert response.status_code == 200
        (question,) = response.json()["questions"]
        assert question["id"] == "text.kind"
        assert question["default"] == "text"
        assert [o["label"] for o in question["options"]] == ["Text", "Song"]
        assert client.get("/sources").json() == []

    def test_create_source(self, client: TestClient) -> None:
        response = client.post("/sources/add", json=TEXT_REQUEST)
        assert response.status_code == 201
        assert len(response.json()["source_ids"]) == 1
        (source,) = client.get("/sources").json()
        assert (source["status"], source["kind"], source["role"]) == ("new", "text", "content")

    def test_create_empty_source(self, client: TestClient) -> None:
        response = client.post("/sources/add", json={"text": "", "answers": TEXT_ANSWER})
        assert response.status_code == 400

    def test_unknown_answer_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/sources/add", json={"text": "Hello", "answers": {"text.kind": "poem"}},
        )
        assert response.status_code == 400

    def test_detect_format_hints_how_input_will_be_read(self, client: TestClient) -> None:
        response = client.post("/sources/detect-format", json={"text": "/tmp/notes.md"})
        assert response.json() == {"format": "markdown", "label": "Text · markdown"}

    def test_source_document_with_marks(self, client: TestClient) -> None:
        source_id = client.post("/sources/add", json=TEXT_REQUEST).json()["source_ids"][0]
        document = client.get(f"/sources/{source_id}/document").json()
        assert document == {
            "blocks": [{
                "type": "paragraph", "lines": [{"text": "Hello world"}], "mode": "flow",
                "level": None, "ordered": None, "depth": None,
            }],
            "highlights": [],
        }

    def test_list_sources(self, client: TestClient) -> None:
        client.post("/sources/add", json={"text": "Text one", "answers": TEXT_ANSWER})
        client.post("/sources/add", json={"text": "Text two", "answers": TEXT_ANSWER})
        response = client.get("/sources")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_process_pending_starts_only_scope(
        self, client: TestClient, db_session: Session, launched: list[int],
    ) -> None:
        ielts = client.post("/collections", json={"name": "IELTS"}).json()
        db_session.add_all([
            SourceModel(title="in", status="new", collection_id=ielts["id"]),
            SourceModel(title="out", status="new"),
        ])
        db_session.commit()
        started = client.post("/sources/process-pending", params={"scope": ielts["id"]})
        assert started.status_code == 202
        titles = {s["id"]: s["title"] for s in client.get("/sources").json()}
        assert [titles[i] for i in started.json()["started"]] == ["in"]
        assert launched == started.json()["started"]

    def test_process_batch_ignores_repeated_ids(
        self, client: TestClient, db_session: Session, launched: list[int],
    ) -> None:
        db_session.add(SourceModel(title="one", status="new"))
        db_session.commit()
        source_id = client.get("/sources").json()[0]["id"]
        response = client.post(
            "/sources/process-batch", json={"source_ids": [source_id, source_id]},
        )
        assert response.status_code == 202
        assert response.json() == {"started": [source_id], "skipped": []}
        assert launched == [source_id]

    def test_process_batch_reports_sources_that_cannot_start(
        self, client: TestClient, db_session: Session, launched: list[int],
    ) -> None:
        db_session.add_all([
            SourceModel(title="new", status="new"),
            SourceModel(title="done", status="done"),
        ])
        db_session.commit()
        ids = {s["title"]: s["id"] for s in client.get("/sources").json()}
        response = client.post(
            "/sources/process-batch", json={"source_ids": [ids["new"], ids["done"]]},
        )
        assert response.status_code == 202
        assert response.json() == {"started": [ids["new"]], "skipped": [ids["done"]]}
        assert launched == [ids["new"]]

    def test_created_at_is_returned_with_utc_offset(self, client: TestClient) -> None:
        """Clients render times in the viewer's zone; they need the offset to do so."""
        before = datetime.now(tz=UTC)
        client.post("/sources/add", json={"text": "Hello", "answers": TEXT_ANSWER})

        created_at = datetime.fromisoformat(client.get("/sources").json()[0]["created_at"])

        assert created_at.utcoffset() == timedelta(0)
        assert abs(created_at - before) < timedelta(minutes=1)

    def test_get_source(self, client: TestClient) -> None:
        create = client.post("/sources/add", json={"text": "Hello", "answers": TEXT_ANSWER})
        source_id = create.json()["source_ids"][0]
        response = client.get(f"/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Hello"

    def test_get_source_not_found(self, client: TestClient) -> None:
        response = client.get("/sources/999")
        assert response.status_code == 404

    def test_process_returns_202(self, client: TestClient) -> None:
        create = client.post(
            "/sources/add", json={"text": "The quick brown fox", "answers": TEXT_ANSWER},
        )
        source_id = create.json()["source_ids"][0]
        response = client.post(f"/sources/{source_id}/process")
        assert response.status_code == 202

    def test_rebuild_runs_in_the_background_and_holds_the_source(
        self, client: TestClient, db_session: Session, spawned: list[object],
    ) -> None:
        source_id = self._processed_source(client, db_session)

        started = client.post(f"/sources/{source_id}/rebuild", json={"include_open": True})

        assert started.status_code == 202
        operation = started.json()
        assert (operation["kind"], operation["state"]) == ("rebuild", "running")
        assert len(spawned) == 1
        state = client.get(f"/sources/{source_id}/operation")
        assert state.status_code == 200
        assert state.json()["operation_id"] == operation["operation_id"]
        assert client.post(f"/sources/{source_id}/rebuild/preview").status_code == 409
        assert client.post(f"/sources/{source_id}/rebuild", json={}).status_code == 409

    def test_rebuild_preview_runs_in_the_background(
        self, client: TestClient, db_session: Session, spawned: list[object],
    ) -> None:
        source_id = self._processed_source(client, db_session)

        started = client.post(f"/sources/{source_id}/rebuild/preview")

        assert started.status_code == 202
        assert (started.json()["kind"], started.json()["state"]) == ("preview", "running")
        assert len(spawned) == 1

    def test_a_topic_is_refreshed_in_the_background(
        self, client: TestClient, db_session: Session, spawned: list[object],
    ) -> None:
        topic_id = client.post("/sources/topic", json={"query": "salary talk"}).json()["id"]
        db_session.query(SourceModel).filter_by(id=topic_id).update({"status": "done"})
        db_session.commit()

        [row] = [s for s in client.get("/sources").json() if s["id"] == topic_id]
        started = client.post(f"/sources/{topic_id}/refresh")

        assert row["available_operation"] == "refresh"
        assert started.status_code == 202
        assert (started.json()["kind"], started.json()["state"]) == ("refresh", "running")
        assert len(spawned) == 1
        assert client.post(f"/sources/{topic_id}/refresh").status_code == 409
        assert client.post(f"/sources/{topic_id}/rebuild", json={}).status_code == 400

    def test_a_content_source_offers_rebuild_and_cannot_be_refreshed(
        self, client: TestClient, db_session: Session,
    ) -> None:
        source_id = self._new_source(client)
        [new] = [s for s in client.get("/sources").json() if s["id"] == source_id]
        db_session.query(SourceModel).filter_by(id=source_id).update({"status": "done"})
        db_session.commit()
        [done] = [s for s in client.get("/sources").json() if s["id"] == source_id]

        assert (new["available_operation"], done["available_operation"]) == (None, "rebuild")
        assert client.post(f"/sources/{source_id}/refresh").status_code == 400

    def test_an_operation_that_never_runs_frees_its_source(
        self, client: TestClient, db_session: Session, _db_engine: object,
    ) -> None:
        source_id = self._new_source(client)
        lock = SqlaSourceOperationLock(db_session)
        lock.acquire(source_id, SourceOperationKind.REBUILD)
        db_session.commit()
        operation = sources_routes.OPERATIONS.started(source_id, SourceOperationKind.REBUILD)

        def broken(_session: Session) -> Callable[[], None]:
            raise RuntimeError("could not build the use case")

        asyncio.run(sources_routes._operation_background(
            source_id, operation.operation_id, sessionmaker(bind=_db_engine), broken,
        ))

        db_session.expire_all()
        assert lock.held(source_id) is None
        state = client.get(f"/sources/{source_id}/operation").json()
        assert (state["state"], state["error"]) == ("error", "could not build the use case")

    def test_a_source_with_no_operation_has_no_operation_state(
        self, client: TestClient,
    ) -> None:
        source_id = self._new_source(client)
        assert client.get(f"/sources/{source_id}/operation").status_code == 404

    def test_rebuild_of_a_missing_source_is_404(self, client: TestClient) -> None:
        assert client.post("/sources/999/rebuild", json={}).status_code == 404

    @staticmethod
    def _new_source(client: TestClient) -> int:
        create = client.post(
            "/sources/add", json={"text": "The quick brown fox", "answers": TEXT_ANSWER},
        )
        source_id: int = create.json()["source_ids"][0]
        return source_id

    def _processed_source(self, client: TestClient, db_session: Session) -> int:
        source_id = self._new_source(client)
        db_session.query(SourceModel).filter_by(id=source_id).update({"status": "done"})
        db_session.commit()
        return source_id

    def test_a_new_source_offers_no_rebuild(
        self, client: TestClient, spawned: list[object],
    ) -> None:
        source_id = self._new_source(client)

        assert client.post(f"/sources/{source_id}/rebuild/preview").status_code == 400
        assert client.post(f"/sources/{source_id}/rebuild", json={}).status_code == 400
        assert spawned == []

    def test_process_not_found(self, client: TestClient) -> None:
        response = client.post("/sources/999/process")
        assert response.status_code == 404

    def test_get_source_candidates_include_frequency_band_and_usage(
        self, client: TestClient, db_session: Session,
    ) -> None:
        source = SourceModel(title="Test text", status="done")
        db_session.add(source)
        db_session.flush()

        candidate = StoredCandidateModel(
            source_id=source.id,
            lemma="gonna",
            pos="VERB",
            zipf_frequency=3.8,
            is_sweet_spot=True,
            occurrences=1,
            status="pending",
            usage_distribution_json=json.dumps({"informal": 0.8, "neutral": 0.2}),
        )
        db_session.add(candidate)
        db_session.flush()
        db_session.add(PhraseModel(
            candidate_id=candidate.id,
            source_phrase=dump_phrase(phrase("I'm gonna do it", "gonna")),
            origin="auto",
            shown_by="selection",
        ))
        db_session.commit()

        response = client.get(f"/sources/{source.id}")
        assert response.status_code == 200
        data = response.json()
        candidates = data["candidates"]
        assert len(candidates) == 1

        c = candidates[0]
        assert c["frequency_band"] == "MID"
        assert c["usage_distribution"] == {"informal": 0.8, "neutral": 0.2}


@pytest.mark.integration
class TestCreateFileSource:
    def test_text_file_creates_source(self, client: TestClient, tmp_path: Path) -> None:
        txt_file = tmp_path / "article.txt"
        txt_file.write_text("Hello world, this is a test article.", encoding="utf-8")

        resp = client.post("/sources/add", json={
            "text": str(txt_file), "title": "Test Article", "answers": TEXT_ANSWER,
        })

        assert resp.status_code == 201
        (source,) = client.get("/sources").json()
        assert (source["title"], source["status"]) == ("Test Article", "new")

    def test_markdown_file_is_text_without_markup(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        md_file = tmp_path / "digest.md"
        md_file.write_text("# Preface\n\n**In short:** a *cautious* scientist.", encoding="utf-8")

        resp = client.post("/sources/add", json={"text": str(md_file), "answers": TEXT_ANSWER})

        assert resp.status_code == 201
        source = client.get("/sources").json()[0]
        assert (source["kind"], source["title"]) == ("text", "digest")
        blocks = client.get(f"/sources/{source['id']}/document").json()["blocks"]
        assert [(b["type"], b["lines"][0]["text"]) for b in blocks] == [
            ("heading", "Preface"), ("paragraph", "In short: a cautious scientist."),
        ]

    def test_binary_file_is_rejected(self, client: TestClient, tmp_path: Path) -> None:
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"%PDF-1.7\x00\x01")

        resp = client.post("/sources/add", json={"text": str(pdf), "answers": TEXT_ANSWER})

        assert resp.status_code == 400
        assert "not a text file" in resp.json()["detail"].lower()

    def test_missing_file_returns_404(self, client: TestClient) -> None:
        resp = client.post("/sources/add", json={"text": "/nonexistent/file.txt"})

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.integration
class TestSavedPhrasesAPI:
    def test_phrase_goes_to_saved_phrases_source_to_learn(self, client: TestClient) -> None:
        response = client.post(
            "/sources/saved-phrases",
            json={"phrase": "She finally gave in to the pressure.", "target_words": [2, 3]},
        )

        assert response.status_code == 201
        candidate = response.json()
        assert candidate["status"] == "learn"
        assert candidate["lemma"] == "give in"
        sources = client.get("/sources").json()
        assert len(sources) == 1
        saved_source = sources[0]
        assert saved_source["title"] == "Saved phrases"
        assert saved_source["role"] == "saved_phrases"
        assert saved_source["is_permanent"] is True
        assert saved_source["learn_count"] == 1
        detail = client.get(f"/sources/{saved_source['id']}").json()
        assert detail["has_source_text"] is False
        assert detail["can_polish_phrases"] is False

    def test_second_phrase_reuses_the_same_source(self, client: TestClient) -> None:
        for text in ("It was a daunting task.", "Keep it concise."):
            last = len(text.split()) - 1
            client.post("/sources/saved-phrases", json={"phrase": text, "target_words": [last]})

        sources = client.get("/sources").json()
        assert len(sources) == 1
        assert sources[0]["candidate_count"] == 2

    def test_target_outside_phrase_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/sources/saved-phrases",
            json={"phrase": "It was a daunting task.", "target_words": [9]},
        )
        assert response.status_code == 400

    def test_saved_phrases_source_cannot_be_deleted_or_rebuilt(
        self, client: TestClient,
    ) -> None:
        client.post(
            "/sources/saved-phrases",
            json={"phrase": "It was a daunting task.", "target_words": [3]},
        )
        source_id = client.get("/sources").json()[0]["id"]

        assert client.delete(f"/sources/{source_id}").status_code == 409
        assert client.post(f"/sources/{source_id}/rebuild", json={}).status_code == 400
        assert client.post(f"/sources/{source_id}/rebuild/preview").status_code == 400


@pytest.mark.integration
class TestBookFileSourceAPI:
    def _book(self, tmp_path: Path) -> Path:
        book = EpubBuilder(title="Dune")
        for n in (1, 2):
            book.add(f"ch{n}.xhtml", page(f"<h1>Chapter {n}</h1><p>{prose(200)}</p>"))
        book.nav = [TocLink(f"Chapter {n}", f"ch{n}.xhtml") for n in (1, 2)]
        return book.write(tmp_path / "dune.epub")

    def test_book_asks_whether_to_split(self, client: TestClient, tmp_path: Path) -> None:
        resp = client.post("/sources/add", json={"text": str(self._book(tmp_path))})

        assert resp.status_code == 200
        (question,) = resp.json()["questions"]
        assert (question["id"], question["prompt"]) == ("book.split", "Add «Dune» as")
        split = question["options"][0]
        assert split["details"]["items"] == [
            {"text": "Dune ch1", "note": "201 words"},
            {"text": "Dune ch2", "note": "201 words"},
        ]
        assert client.get("/sources").json() == []

    def test_split_book_becomes_a_collection_of_chapters(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post(
            "/sources/add",
            json={"text": str(self._book(tmp_path)), "answers": {"book.split": "split"}},
        )

        assert resp.status_code == 201
        assert len(resp.json()["source_ids"]) == 2
        sources = client.get("/sources").json()
        assert [s["title"] for s in sources] == ["Dune ch1", "Dune ch2"]
        assert {tuple(s["collection_path"]) for s in sources} == {("Dune",)}
        assert {s["kind"] for s in sources} == {"book"}

    def test_path_copied_from_a_shell_is_accepted(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post("/sources/add", json={"text": f"'{self._book(tmp_path)}'"})

        assert resp.status_code == 200
        assert resp.json()["questions"][0]["id"] == "book.split"

    def test_broken_book_is_rejected(self, client: TestClient, tmp_path: Path) -> None:
        path = tmp_path / "broken.epub"
        path.write_text("not a book")

        resp = client.post("/sources/add", json={"text": str(path)})

        assert resp.status_code == 400
