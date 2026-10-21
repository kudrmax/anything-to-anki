from __future__ import annotations

import json
from collections.abc import Coroutine, Generator  # noqa: TC003
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.api.routes import operations as operations_routes
from backend.infrastructure.api.routes import sources as sources_routes
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    PhraseModel,
    SourceModel,
    StoredCandidateModel,
    dump_phrase,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tests.phrase_support import phrase
from tests.projection_support import rebuild_projection
from tests.review_window_support import open_review, review_list, set_texts
from tests.unit.infrastructure.epub.epub_builder import EpubBuilder, TocLink, page, prose
from tests.word_support import TEST_SECTION


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


@pytest.fixture()
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Background operations started by the routes; none of them runs."""
    started: list[object] = []

    def record(work: Coroutine[object, object, None]) -> None:
        work.close()
        started.append(work)

    monkeypatch.setattr(sources_routes, "in_background", record)
    monkeypatch.setattr(operations_routes, "in_background", record)
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
TEXT_REQUEST = {"text": "Hello world", "answers": [TEXT_ANSWER]}


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
        response = client.post("/sources/add", json={"text": "", "answers": [TEXT_ANSWER]})
        assert response.status_code == 400

    def test_unknown_answer_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/sources/add", json={"text": "Hello", "answers": [{"text.kind": "poem"}]},
        )
        assert response.status_code == 400

    def test_describe_input_says_what_it_becomes(self, client: TestClient) -> None:
        text = "She shrugged off the comment."
        response = client.post("/sources/describe-input", json={"text": text})
        assert response.json() == {
            "kind": "phrase", "format": None, "several": None, "label": None,
            "problem": None, "problem_message": None, "problem_hint": None,
        }

    def test_describe_input_reports_a_missing_file(self, client: TestClient) -> None:
        response = client.post("/sources/describe-input", json={"text": "/no/such/notes.md"})
        assert (response.json()["kind"], response.json()["problem"]) == (None, "file_not_found")

    def test_source_document_with_marks(self, client: TestClient) -> None:
        source_id = client.post("/sources/add", json=TEXT_REQUEST).json()["source_ids"][0]
        [document] = set_texts(client, f"source-{source_id}")
        assert document["size_hint"] > 0
        assert {k: v for k, v in document.items() if k != "size_hint"} == {
            "source_id": source_id,
            "title": "Hello world",
            "blocks": [{
                "type": "paragraph", "lines": [{"text": "Hello world"}], "mode": "flow",
                "level": None, "ordered": None, "depth": None, "number": None,
            }],
            "highlights": [],
        }

    def test_list_sources(self, client: TestClient) -> None:
        client.post("/sources/add", json={"text": "Text one", "answers": [TEXT_ANSWER]})
        client.post("/sources/add", json={"text": "Text two", "answers": [TEXT_ANSWER]})
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
        client.post("/sources/add", json={"text": "Hello", "answers": [TEXT_ANSWER]})

        created_at = datetime.fromisoformat(client.get("/sources").json()[0]["created_at"])

        assert created_at.utcoffset() == timedelta(0)
        assert abs(created_at - before) < timedelta(minutes=1)

    def test_get_source(self, client: TestClient) -> None:
        create = client.post("/sources/add", json={"text": "Hello", "answers": [TEXT_ANSWER]})
        source_id = create.json()["source_ids"][0]
        assert open_review(client, f"source-{source_id}")["header"]["title"] == "Hello"

    def test_get_source_not_found(self, client: TestClient) -> None:
        response = client.post("/api/review", json={"scope": "source-999"})
        assert response.status_code == 404

    def test_process_returns_202(self, client: TestClient) -> None:
        create = client.post(
            "/sources/add", json={"text": "The quick brown fox", "answers": [TEXT_ANSWER]},
        )
        source_id = create.json()["source_ids"][0]
        response = client.post(f"/sources/{source_id}/process")
        assert response.status_code == 202

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
            usage_distribution_json=json.dumps({"informal": 0.8, "neutral": 0.2}),
        )
        db_session.add(candidate)
        db_session.flush()
        db_session.add(PhraseModel(
            candidate_id=candidate.id,
            source_phrase=dump_phrase(phrase("I'm gonna do it", "gonna")),
            origin="auto",
            shown_by="selection",
            earned_section=TEST_SECTION,
        ))
        db_session.commit()
        rebuild_projection(db_session)

        candidates = review_list(client, f"source-{source.id}")
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
            "text": str(txt_file), "title": "Test Article", "answers": [TEXT_ANSWER],
        })

        assert resp.status_code == 201
        (source,) = client.get("/sources").json()
        assert (source["title"], source["status"]) == ("Test Article", "new")

    def test_markdown_file_is_text_without_markup(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        md_file = tmp_path / "digest.md"
        md_file.write_text("# Preface\n\n**In short:** a *cautious* scientist.", encoding="utf-8")

        resp = client.post("/sources/add", json={"text": str(md_file), "answers": [TEXT_ANSWER]})

        assert resp.status_code == 201
        source = client.get("/sources").json()[0]
        assert (source["kind"], source["title"]) == ("text", "digest")
        [document] = set_texts(client, f"source-{source['id']}")
        blocks = document["blocks"]
        assert [(b["type"], b["lines"][0]["text"]) for b in blocks] == [
            ("heading", "Preface"), ("paragraph", "In short: a cautious scientist."),
        ]

    def test_binary_file_is_rejected(self, client: TestClient, tmp_path: Path) -> None:
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"%PDF-1.7\x00\x01")

        resp = client.post("/sources/add", json={"text": str(pdf), "answers": [TEXT_ANSWER]})

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
        assert (candidate["choice"], candidate["shown"]["status"]) == ("learn", "learn")
        assert candidate["lemma"] == "give in"
        sources = client.get("/sources").json()
        assert len(sources) == 1
        saved_source = sources[0]
        assert saved_source["title"] == "Saved phrases"
        assert saved_source["role"] == "saved_phrases"
        assert saved_source["is_permanent"] is True
        assert saved_source["learn_count"] == 1
        [card] = review_list(client, f"source-{saved_source['id']}")
        assert card["source"]["can_polish_phrases"] is False
        assert set_texts(client, f"source-{saved_source['id']}") == []

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

    def test_saved_phrases_source_cannot_be_deleted_but_can_be_rebuilt(
        self, client: TestClient, spawned: list[object],
    ) -> None:
        client.post(
            "/sources/saved-phrases",
            json={"phrase": "It was a daunting task.", "target_words": [3]},
        )
        source_id = client.get("/sources").json()[0]["id"]

        [saved] = client.get("/sources").json()
        assert client.delete(f"/sources/{source_id}").status_code == 409
        assert saved["available_operations"] == ["update"]
        assert client.post(
            "/api/operations/preview", params={"scope": f"source-{source_id}", "of": "update"},
        ).status_code == 202
        assert client.post(
            "/api/operations/preview", params={"scope": f"source-{source_id}", "of": "recut"},
        ).status_code == 400


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
        assert question["options"][0]["details"] is None
        assert client.get("/sources").json() == []

    def test_split_book_asks_how_to_name_chapters(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post(
            "/sources/add",
            json={"text": str(self._book(tmp_path)), "answers": [{"book.split": "split"}]},
        )

        assert resp.status_code == 200
        assert resp.json()["heading"] == "Add «Dune»"
        assert resp.json()["default_collection"] == {"existing_id": None, "new_name": "Dune"}
        assert client.get("/sources").json() == []

    def test_named_chapters_become_a_collection(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post(
            "/sources/add",
            json={
                "text": str(self._book(tmp_path)),
                "answers": [{"book.split": "split"}],
                "naming": {"collection": {"new_name": "Dune"}, "rule": "{{collection}} ch{{n}}"},
            },
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


class TestBatchSourceAPI:
    def _files(self, tmp_path: Path, *names: str) -> str:
        for name in names:
            (tmp_path / name).write_text(f"The story of {name} begins here.")
        return "\n".join(str(tmp_path / name) for name in names)

    def test_several_files_ask_how_to_name_them(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post(
            "/sources/add",
            json={"text": self._files(tmp_path, "b.txt", "a.txt"), "answers": [TEXT_ANSWER] * 2},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["heading"] == "Add 2 files"
        assert [item["label"] for item in body["items"]] == ["a.txt", "b.txt"]

    def test_named_files_are_added_with_hand_edited_rows(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        resp = client.post(
            "/sources/add",
            json={
                "text": self._files(tmp_path, "a.txt", "b.txt"),
                "answers": [TEXT_ANSWER] * 2,
                "naming": {"collection": None, "rule": "Part {{n}}", "titles": {"1": "Intro"}},
            },
        )

        assert resp.status_code == 201
        assert [s["title"] for s in client.get("/sources").json()] == ["Part 1", "Intro"]

    def test_bad_rule_is_rejected(self, client: TestClient, tmp_path: Path) -> None:
        resp = client.post(
            "/sources/add",
            json={
                "text": self._files(tmp_path, "a.txt", "b.txt"),
                "answers": [TEXT_ANSWER] * 2,
                "naming": {"collection": None, "rule": "Part"},
            },
        )

        assert resp.status_code == 422

    def test_a_bad_file_names_itself(self, client: TestClient, tmp_path: Path) -> None:
        text = self._files(tmp_path, "a.txt")
        (tmp_path / "picture.txt").write_bytes(b"\x00\x01\xff")

        resp = client.post(
            "/sources/add",
            json={"text": f"{text}\n{tmp_path / 'picture.txt'}", "answers": [TEXT_ANSWER] * 2},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("picture.txt: ")


class TestRenderNamesAPI:
    def test_renders_titles(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/render-names",
            json={"rule": "{{collection}} ch{{n}}", "own_titles": ["a", "b"]},
        )

        assert resp.status_code == 200
        assert resp.json() == ["ch1", "ch2"]

    def test_bad_rule_is_explained(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/render-names",
            json={"rule": "{{collection}}", "collection_name": None, "own_titles": ["a"]},
        )

        assert resp.status_code == 422
        assert "must contain" in resp.json()["detail"]["message"]

    def test_renders_numbers_with_fixed_digits(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/render-names",
            json={"rule": "ch{{n}}", "own_titles": ["a", "b"], "number_digits": 2},
        )

        assert resp.json() == ["ch01", "ch02"]

    def test_adds_with_fixed_digits(self, client: TestClient, tmp_path: Path) -> None:
        for name in ("a.txt", "b.txt"):
            (tmp_path / name).write_text(f"The story of {name} begins here.")
        resp = client.post(
            "/sources/add",
            json={
                "text": f"{tmp_path / 'a.txt'}\n{tmp_path / 'b.txt'}",
                "answers": [TEXT_ANSWER] * 2,
                "naming": {"rule": "ch{{n}}", "number_digits": 3},
            },
        )

        assert resp.status_code == 201
        assert [s["title"] for s in client.get("/sources").json()] == ["ch001", "ch002"]
