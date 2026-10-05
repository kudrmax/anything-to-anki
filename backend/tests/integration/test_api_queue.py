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
    session: Session,
    job_id: int,
    candidate_id: int,
    source_id: int,
    job_type: str = "meaning",
    status: str = "queued",
    error: str | None = None,
    created_at: str = "2026-01-01 00:00:00",
    started_at: str | None = None,
) -> None:
    session.execute(
        text(
            "INSERT INTO jobs "
            "(id, job_type, candidate_id, source_id, status, error, created_at, started_at) "
            "VALUES (:id, :jt, :cid, :sid, :status, :error, :created_at, :started_at)"
        ),
        {
            "id": job_id,
            "jt": job_type,
            "cid": candidate_id,
            "sid": source_id,
            "status": status,
            "error": error,
            "created_at": created_at,
            "started_at": started_at,
        },
    )
    session.flush()


def _seed(session: Session) -> None:
    """Two sources: a running TTS, queued meanings, failures of two kinds."""
    _insert_source(session, 1, "Alpha")
    _insert_source(session, 2, "Beta")
    for cid, sid in ((1, 1), (2, 1), (3, 2), (4, 1), (5, 2), (6, 2)):
        _insert_candidate(session, cid, sid)
    _insert_job(session, 1, 1, 1, job_type="tts", status="running",
                created_at="2026-01-01 00:00:00", started_at="2026-01-01 00:00:01")
    _insert_job(session, 2, 2, 1, job_type="meaning", created_at="2026-01-01 00:00:02")
    _insert_job(session, 3, 3, 2, job_type="meaning", created_at="2026-01-01 00:00:03")
    _insert_job(session, 4, 4, 1, job_type="meaning", status="failed", error="timeout")
    _insert_job(session, 5, 5, 2, job_type="meaning", status="failed", error="timeout")
    _insert_job(session, 6, 6, 2, job_type="polish", status="failed", error=None)
    session.commit()


def _active_ids(client: TestClient) -> list[int]:
    queue = client.get("/api/queue").json()
    return [j["job_id"] for j in queue["running"] + queue["queued"]]


# ── snapshot ────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestQueueSnapshot:
    def test_empty_queue(self, client: TestClient) -> None:
        assert client.get("/api/queue").json() == {
            "counts": [], "total_queued": 0, "total_running": 0, "total_failed": 0,
            "running": [], "queued": [], "failed": [],
        }

    def test_counts_jobs_by_type_in_pipeline_order(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        queue = client.get("/api/queue").json()

        assert queue["counts"] == [
            {"job_type": "polish", "queued": 0, "running": 0, "failed": 1},
            {"job_type": "meaning", "queued": 2, "running": 0, "failed": 2},
            {"job_type": "tts", "queued": 0, "running": 1, "failed": 0},
        ]
        assert (queue["total_queued"], queue["total_running"], queue["total_failed"]) == (2, 1, 3)

    def test_lists_running_and_queued_jobs_in_line(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        queue = client.get("/api/queue").json()

        assert [(j["job_id"], j["status"], j["position"]) for j in queue["running"]] == [
            (1, "running", None),
        ]
        assert [(j["job_id"], j["position"], j["source_title"]) for j in queue["queued"]] == [
            (2, 1, "Alpha"), (3, 2, "Beta"),
        ]

    def test_queued_limit_caps_the_list_but_not_the_total(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        queue = client.get("/api/queue?queued_limit=1").json()

        assert [j["job_id"] for j in queue["queued"]] == [2]
        assert queue["total_queued"] == 2

    def test_groups_failures_by_type_and_error(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        failed = client.get("/api/queue").json()["failed"]

        assert failed == [
            {"job_type": "polish", "total_failed": 1, "groups": [
                {"error_text": "Unknown error", "count": 1, "sources": [
                    {"source_id": 2, "source_title": "Beta", "count": 1},
                ]},
            ]},
            {"job_type": "meaning", "total_failed": 2, "groups": [
                {"error_text": "timeout", "count": 2, "sources": [
                    {"source_id": 1, "source_title": "Alpha", "count": 1},
                    {"source_id": 2, "source_title": "Beta", "count": 1},
                ]},
            ]},
        ]

    def test_filtered_by_source(self, client: TestClient, db_session: Session) -> None:
        _seed(db_session)

        queue = client.get("/api/queue?source_id=2").json()

        assert [j["job_id"] for j in queue["queued"]] == [3]
        assert queue["running"] == []
        assert queue["total_failed"] == 2


# ── actions ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestQueueActions:
    def test_cancel_single_running_job(self, client: TestClient, db_session: Session) -> None:
        _seed(db_session)

        response = client.post("/api/queue/cancel", json={"job_id": 1})

        assert response.json() == {"affected": 1}
        assert _active_ids(client) == [2, 3]

    def test_cancel_missing_job_affects_nothing(self, client: TestClient) -> None:
        assert client.post("/api/queue/cancel", json={"job_id": 999}).json() == {"affected": 0}

    def test_cancel_by_type_and_source(self, client: TestClient, db_session: Session) -> None:
        _seed(db_session)

        response = client.post("/api/queue/cancel", json={"job_type": "meaning", "source_id": 2})

        assert response.json() == {"affected": 1}
        assert _active_ids(client) == [1, 2]

    def test_cancel_everything_keeps_failures(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        assert client.post("/api/queue/cancel", json={}).json() == {"affected": 3}
        assert _active_ids(client) == []
        assert client.get("/api/queue").json()["total_failed"] == 3

    def test_unknown_job_type_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/queue/cancel", json={"job_type": "nope"})
        assert response.status_code == 422

    def test_retry_by_error_moves_failures_to_the_end_of_the_line(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        response = client.post("/api/queue/retry", json={"error_text": "timeout"})

        assert response.json() == {"affected": 2}
        queue = client.get("/api/queue").json()
        assert [j["job_id"] for j in queue["queued"]] == [2, 3, 4, 5]
        assert queue["total_failed"] == 1

    def test_retry_unknown_error_group(self, client: TestClient, db_session: Session) -> None:
        _seed(db_session)

        response = client.post(
            "/api/queue/retry", json={"job_type": "polish", "error_text": "Unknown error"},
        )

        assert response.json() == {"affected": 1}

    def test_dismiss_removes_failures_without_retrying(
        self, client: TestClient, db_session: Session,
    ) -> None:
        _seed(db_session)

        response = client.post("/api/queue/dismiss", json={"job_type": "meaning", "source_id": 1})

        assert response.json() == {"affected": 1}
        queue = client.get("/api/queue").json()
        assert queue["total_failed"] == 2
        assert _active_ids(client) == [1, 2, 3]
