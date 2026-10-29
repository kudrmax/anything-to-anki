from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tests.projection_support import rebuild_projection
from tests.review_support import on_review
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator

# ── fixtures ────────────────────────────────────────────────────────────────


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


# ── DB helpers ───────────────────────────────────────────────────────────────


def _insert_source(session: Session, source_id: int, title: str | None = None) -> None:
    session.execute(
        text(
            "INSERT INTO sources "
            "(id, title, status, created_at) "
            "VALUES (:id, :title, 'new', '2026-01-01 00:00:00')"
        ),
        {"id": source_id, "title": title},
    )
    session.flush()


def _insert_candidate(session: Session, candidate_id: int, source_id: int) -> None:
    insert_word(session, candidate_id, source_id=source_id)
    session.flush()


def _insert_job(
    session: Session, job_id: int, candidate_id: int, source_id: int, status: str,
) -> None:
    session.execute(
        text(
            "INSERT INTO jobs (id, job_type, candidate_id, source_id, status, created_at,"
            " phrase_id, phrase_revision)"
            " VALUES (:id, 'meaning', :cid, :sid, :status, '2026-01-01 00:00:00', :pid, 0)"
        ),
        {
            "id": job_id, "cid": candidate_id, "sid": source_id, "status": status,
            "pid": phrase_id_of(candidate_id),
        },
    )
    session.flush()


def _insert_meaning(session: Session, candidate_id: int) -> None:
    session.execute(
        text(
            "INSERT INTO candidate_meanings (phrase_id, meaning, translation, synonyms) "
            "VALUES (:pid, 'm', 't', 's')"
        ),
        {"pid": phrase_id_of(candidate_id)},
    )
    session.flush()


@pytest.fixture()
def seeded(db_session: Session) -> None:
    """Source 1: card 1 has a meaning, 2 has none, 3 is queued, 4 failed."""
    _insert_source(db_session, 1)
    for cid in (1, 2, 3, 4):
        _insert_candidate(db_session, cid, 1)
    _insert_meaning(db_session, 1)
    _insert_job(db_session, 30, 3, 1, "queued")
    _insert_job(db_session, 40, 4, 1, "failed")
    db_session.commit()
    rebuild_projection(db_session)


SECOND_PHRASE = phrase_id_of(2)
_SELECTION = {
    "start_block": 0, "start_line": 0, "start_char": 0,
    "end_block": 0, "end_line": 0, "end_char": 5,
}


def _queued(db_session: Session) -> int:
    """The meaning jobs on their way."""
    count: int = db_session.execute(text(
        "SELECT count(*) FROM jobs WHERE job_type = 'meaning' AND status = 'queued'"
    )).scalar_one()
    return count


def _meaning_status(client: TestClient) -> dict[str, object]:
    status = client.get("/api/review/generation", params={"scope": "source-1"}).json()
    return next(k for k in status["kinds"] if k["kind"] == "meaning")


COLLECTION = 7


@pytest.fixture()
def in_collection(db_session: Session) -> None:
    """Source 2 with card 5 (no meaning); collection 7 holds sources 1 and 2."""
    db_session.execute(text(
        "INSERT INTO collections (id, name, position, created_at)"
        " VALUES (:id, 'Show', 0, '2026-01-01 00:00:00')"
    ), {"id": COLLECTION})
    _insert_source(db_session, 2)
    _insert_candidate(db_session, 5, 2)
    db_session.execute(
        text("UPDATE sources SET collection_id = :c WHERE id IN (1, 2)"), {"c": COLLECTION},
    )
    db_session.commit()
    rebuild_projection(db_session)


def _hold(session: Session, source_id: int, kind: str) -> None:
    session.execute(text(
        "INSERT INTO source_operations (source_id, kind, started_at)"
        " VALUES (:id, :kind, '2026-01-01 00:00:00')"
    ), {"id": source_id, "kind": kind})
    session.commit()


@pytest.mark.integration
@pytest.mark.usefixtures("seeded", "in_collection")
class TestGenerationOnASet:
    def test_busy_source_is_skipped_in_a_collection(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _hold(db_session, 1, "update")
        response = on_review(
            client, "POST", "/api/review/generation/meaning",
            params={"scope": "7", "cards": "missing"},
        )
        assert response.status_code == 202
        assert _queued(db_session) == 2

    def test_all_sources_busy_is_409(self, client: TestClient, db_session: Session) -> None:
        _hold(db_session, 1, "update")
        _hold(db_session, 2, "update")
        response = on_review(
            client, "POST", "/api/review/generation/meaning",
            params={"scope": "7", "cards": "missing"},
        )
        assert response.status_code == 409

    def test_status_sums_sources(self, client: TestClient) -> None:
        status = client.get("/api/review/generation", params={"scope": "7"}).json()
        meaning = next(k for k in status["kinds"] if k["kind"] == "meaning")
        assert (meaning["total"], meaning["missing"]) == (5, 2)
        assert status["in_progress"] is True

    def test_cancel_covers_the_set(self, client: TestClient, db_session: Session) -> None:
        response = on_review(
            client, "POST", "/api/review/generation/meaning/cancel", params={"scope": "7"},
        )
        assert response.status_code == 200
        assert _queued(db_session) == 0

    def test_unsorted_is_400(self, client: TestClient) -> None:
        status = client.get("/api/review/generation", params={"scope": "unsorted"})
        assert status.status_code == 400
        assert on_review(
            client, "POST", "/api/review/generation/meaning",
            params={"scope": "unsorted", "cards": "missing"},
        ).status_code == 400

    def test_old_generation_routes_are_gone(self, client: TestClient) -> None:
        assert client.get("/sources/1/generation").status_code in (404, 405)
        assert client.post("/sources/1/generation/meaning?scope=missing").status_code == 404


@pytest.mark.integration
@pytest.mark.usefixtures("seeded")
class TestGenerationApi:
    def test_status_splits_cards_by_where_they_stand(self, client: TestClient) -> None:
        response = client.get("/api/review/generation", params={"scope": "source-1"})

        assert response.status_code == 200
        body = response.json()
        assert [k["kind"] for k in body["kinds"]] == ["polish", "meaning", "pronunciation", "tts"]
        assert body["in_progress"] is True
        assert body["batch_size"] == 100
        assert _meaning_status(client) == {
            "kind": "meaning", "total": 4, "done": 1, "running": 1, "failed": 1,
            "next": 1, "missing": 1, "ready_next": 1, "ready_missing": 1, "ready_all": 3, "all": 3,
            "blocked_by": None, "videos_to_download": 0,
        }

    def test_generate_missing_then_retry_failed(
        self, client: TestClient, db_session: Session,
    ) -> None:
        missing = on_review(
            client, "POST", "/api/review/generation/meaning?scope=source-1&cards=missing",
        )
        assert missing.status_code == 202
        assert _queued(db_session) == 2

        failed = on_review(
            client, "POST", "/api/review/generation/meaning?scope=source-1&cards=failed",
        )
        assert failed.status_code == 202
        assert _queued(db_session) == 3

        status = _meaning_status(client)
        assert (status["done"], status["running"], status["failed"], status["missing"]) == (
            1, 3, 0, 0,
        )

    def test_regenerate_all_drops_old_meanings(
        self, client: TestClient, db_session: Session,
    ) -> None:
        response = on_review(
            client, "POST", "/api/review/generation/meaning?scope=source-1&cards=all",
        )

        assert response.status_code == 202
        assert _queued(db_session) == 4
        status = _meaning_status(client)
        assert (status["done"], status["running"]) == (0, 4)

    def test_cancel_stops_the_kind(self, client: TestClient, db_session: Session) -> None:
        response = on_review(
            client, "POST", "/api/review/generation/meaning/cancel?scope=source-1",
        )

        assert response.status_code == 200
        assert _queued(db_session) == 0
        assert _meaning_status(client)["running"] == 0

    def test_kind_the_source_has_no_use_for_is_400(self, client: TestClient) -> None:
        response = on_review(
            client, "POST", "/api/review/generation/media?scope=source-1&cards=missing",
        )
        assert response.status_code == 400

    def test_unknown_scope_is_422(self, client: TestClient) -> None:
        response = on_review(
            client, "POST", "/api/review/generation/meaning?scope=source-1&cards=some",
        )
        assert response.status_code == 422

    def test_unknown_source_is_404(self, client: TestClient) -> None:
        status = client.get("/api/review/generation", params={"scope": "source-99"})
        assert status.status_code == 404

    def test_a_source_being_rebuilt_is_409_and_queues_nothing(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _hold(db_session, 1, "update")

        response = on_review(
            client, "POST", "/api/review/generation/meaning?scope=source-1&cards=missing",
        )
        assert response.status_code == 409
        assert on_review(
            client, "POST", f"/phrases/{SECOND_PHRASE}/generate-tts",
        ).status_code == 409
        assert _meaning_status(client)["missing"] == 1

    @pytest.mark.parametrize(("method", "path", "body"), [
        ("post", f"/phrases/{SECOND_PHRASE}/decision", {"button": "learn"}),
        ("put", f"/phrases/{SECOND_PHRASE}/phrase-boundary", {"selection": _SELECTION}),
        (
            "post", f"/phrases/{SECOND_PHRASE}/replace-with-example",
            {"example_text": "A word2 here."},
        ),
        ("post", f"/phrases/{SECOND_PHRASE}/replace-with-target", {}),
        ("put", f"/phrases/{SECOND_PHRASE}/cloze", {
            "phrase": "word2", "hidden_word_indices": [0], "hint_kind": "none",
        }),
        ("post", "/sources/1/candidates/manual", {"target_words": [0], "selection": _SELECTION}),
    ])
    def test_manual_phrase_changes_wait_for_the_rebuild(
        self, client: TestClient, db_session: Session, method: str, path: str,
        body: dict[str, object],
    ) -> None:
        db_session.execute(text(
            "INSERT INTO source_operations (source_id, kind, started_at)"
            " VALUES (1, 'update', '2026-01-01 00:00:00')"
        ))
        db_session.commit()

        response = on_review(client, method, path, json=body)

        assert response.status_code == 409, response.text
        phrase = db_session.execute(text(
            "SELECT choice, edited_by_user FROM phrases WHERE id = :id"
        ), {"id": SECOND_PHRASE}).one()
        assert tuple(phrase) == ("none", 0)
        assert db_session.execute(text("SELECT COUNT(*) FROM phrases")).scalar_one() == 4
