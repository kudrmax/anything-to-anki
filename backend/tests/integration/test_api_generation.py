from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

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
            "(id, raw_text, title, status, input_method, content_type, created_at) "
            "VALUES (:id, 'text', :title, 'new', 'text_pasted', 'text', '2026-01-01 00:00:00')"
        ),
        {"id": source_id, "title": title},
    )
    session.flush()


def _insert_candidate(session: Session, candidate_id: int, source_id: int) -> None:
    session.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, "
            "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
            "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
            "VALUES (:id, :sid, 'word', 'NOUN', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
        ),
        {"id": candidate_id, "sid": source_id},
    )
    session.flush()


def _insert_job(
    session: Session, job_id: int, candidate_id: int, source_id: int, status: str,
) -> None:
    session.execute(
        text(
            "INSERT INTO jobs (id, job_type, candidate_id, source_id, status, created_at) "
            "VALUES (:id, 'meaning', :cid, :sid, :status, '2026-01-01 00:00:00')"
        ),
        {"id": job_id, "cid": candidate_id, "sid": source_id, "status": status},
    )
    session.flush()


def _insert_meaning(session: Session, candidate_id: int) -> None:
    session.execute(
        text(
            "INSERT INTO candidate_meanings (candidate_id, meaning, translation, synonyms) "
            "VALUES (:cid, 'm', 't', 's')"
        ),
        {"cid": candidate_id},
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


def _meaning_status(client: TestClient) -> dict[str, object]:
    status = client.get("/sources/1/generation").json()
    return next(k for k in status["kinds"] if k["kind"] == "meaning")


@pytest.mark.integration
@pytest.mark.usefixtures("seeded")
class TestGenerationApi:
    def test_status_splits_cards_by_where_they_stand(self, client: TestClient) -> None:
        response = client.get("/sources/1/generation")

        assert response.status_code == 200
        body = response.json()
        assert [k["kind"] for k in body["kinds"]] == ["polish", "meaning", "pronunciation", "tts"]
        assert body["in_progress"] is True
        assert _meaning_status(client) == {
            "kind": "meaning", "total": 4, "done": 1, "running": 1, "failed": 1, "missing": 1,
            "blocked_by": None,
        }

    def test_generate_missing_then_retry_failed(self, client: TestClient) -> None:
        missing = client.post("/sources/1/generation/meaning?scope=missing")
        assert missing.status_code == 202
        assert missing.json() == {"enqueued": 1}

        failed = client.post("/sources/1/generation/meaning?scope=failed")
        assert failed.json() == {"enqueued": 1}

        status = _meaning_status(client)
        assert (status["done"], status["running"], status["failed"], status["missing"]) == (
            1, 3, 0, 0,
        )

    def test_regenerate_all_drops_old_meanings(self, client: TestClient) -> None:
        response = client.post("/sources/1/generation/meaning?scope=all")

        assert response.json() == {"enqueued": 3}
        status = _meaning_status(client)
        assert (status["done"], status["running"]) == (0, 4)

    def test_cancel_stops_the_kind(self, client: TestClient) -> None:
        response = client.post("/sources/1/generation/meaning/cancel")

        assert response.json() == {"cancelled": 1}
        assert _meaning_status(client)["running"] == 0

    def test_kind_the_source_has_no_use_for_is_400(self, client: TestClient) -> None:
        assert client.post("/sources/1/generation/media?scope=missing").status_code == 400

    def test_unknown_scope_is_422(self, client: TestClient) -> None:
        assert client.post("/sources/1/generation/meaning?scope=some").status_code == 422

    def test_unknown_source_is_404(self, client: TestClient) -> None:
        assert client.get("/sources/99/generation").status_code == 404
