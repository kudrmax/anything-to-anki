from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


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
            "INSERT INTO sources (id, raw_text, title, status, input_method, content_type, created_at) "
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
            "INSERT INTO jobs (id, job_type, candidate_id, source_id, status, error, created_at, started_at) "
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


# ── global-summary ───────────────────────────────────────────────────────────


@pytest.mark.integration
class TestGlobalSummary:
    def test_returns_zeros_when_no_jobs(self, client: TestClient) -> None:
        response = client.get("/api/queue/global-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["meaning"] == {"queued": 0, "running": 0, "failed": 0}
        assert data["media"] == {"queued": 0, "running": 0, "failed": 0}
        assert data["pronunciation"] == {"queued": 0, "running": 0, "failed": 0}
        assert data["video_download"] == {"queued": 0, "running": 0, "failed": 0}

    def test_returns_correct_counts(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="queued")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="failed", error="oops")
        _insert_job(db_session, 3, 3, 1, job_type="media", status="running", started_at="2026-01-01 01:00:00")
        db_session.commit()

        response = client.get("/api/queue/global-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["meaning"]["queued"] == 1
        assert data["meaning"]["failed"] == 1
        assert data["meaning"]["running"] == 0
        assert data["media"]["running"] == 1
        assert data["media"]["queued"] == 0

    def test_filtered_by_source_id(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="queued")
        _insert_job(db_session, 2, 2, 2, job_type="meaning", status="queued")
        db_session.commit()

        response = client.get("/api/queue/global-summary?source_id=1")
        assert response.status_code == 200
        data = response.json()
        assert data["meaning"]["queued"] == 1  # only source 1


# ── order ────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestQueueOrder:
    def test_returns_empty_when_no_jobs(self, client: TestClient) -> None:
        response = client.get("/api/queue/order")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] == []
        assert data["queued"] == []
        assert data["total_queued"] == 0

    def test_returns_running_and_queued(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1, title="My Source")
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_job(db_session, 1, 1, 1, status="running", started_at="2026-01-01 01:00:00")
        _insert_job(db_session, 2, 2, 1, status="queued")
        db_session.commit()

        response = client.get("/api/queue/order")
        assert response.status_code == 200
        data = response.json()
        assert len(data["running"]) == 1
        assert len(data["queued"]) == 1
        assert data["total_queued"] == 1
        assert data["running"][0]["source_title"] == "My Source"
        assert data["queued"][0]["position"] == 1

    def test_queued_positions_are_sequential(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        _insert_job(db_session, 1, 1, 1, status="queued", created_at="2026-01-01 00:00:01")
        _insert_job(db_session, 2, 2, 1, status="queued", created_at="2026-01-01 00:00:02")
        _insert_job(db_session, 3, 3, 1, status="queued", created_at="2026-01-01 00:00:03")
        db_session.commit()

        response = client.get("/api/queue/order")
        assert response.status_code == 200
        data = response.json()
        positions = [j["position"] for j in data["queued"]]
        assert positions == [1, 2, 3]

    def test_filtered_by_source_id(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, status="queued")
        _insert_job(db_session, 2, 2, 2, status="queued")
        db_session.commit()

        response = client.get("/api/queue/order?source_id=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["queued"]) == 1
        assert data["queued"][0]["source_id"] == 1

    def test_failed_jobs_are_excluded(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_job(db_session, 1, 1, 1, status="failed", error="boom")
        db_session.commit()

        response = client.get("/api/queue/order")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] == []
        assert data["queued"] == []

    def test_limit_param(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        for i in range(1, 6):
            _insert_candidate(db_session, i, 1)
            _insert_job(db_session, i, i, 1, status="queued", created_at=f"2026-01-01 00:00:0{i}")
        db_session.commit()

        response = client.get("/api/queue/order?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["queued"]) == 2
        assert data["total_queued"] == 5


# ── failed ───────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestQueueFailed:
    def test_returns_empty_when_no_failures(self, client: TestClient) -> None:
        response = client.get("/api/queue/failed")
        assert response.status_code == 200
        data = response.json()
        assert data["types"] == []

    def test_returns_failed_jobs_grouped(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1, title="Source One")
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="timeout")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="failed", error="timeout")
        db_session.commit()

        response = client.get("/api/queue/failed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["types"]) == 1
        type_entry = data["types"][0]
        assert type_entry["job_type"] == "meaning"
        assert type_entry["total_failed"] == 2
        assert len(type_entry["groups"]) == 1
        assert type_entry["groups"][0]["error_text"] == "timeout"
        assert type_entry["groups"][0]["count"] == 2

    def test_groups_by_error_text(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="error A")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="failed", error="error B")
        _insert_job(db_session, 3, 3, 1, job_type="meaning", status="failed", error="error A")
        db_session.commit()

        response = client.get("/api/queue/failed")
        assert response.status_code == 200
        data = response.json()
        type_entry = data["types"][0]
        assert type_entry["total_failed"] == 3
        groups_by_error = {g["error_text"]: g for g in type_entry["groups"]}
        assert groups_by_error["error A"]["count"] == 2
        assert groups_by_error["error B"]["count"] == 1

    def test_groups_by_job_type(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="err")
        _insert_job(db_session, 2, 2, 1, job_type="media", status="failed", error="err")
        db_session.commit()

        response = client.get("/api/queue/failed")
        assert response.status_code == 200
        data = response.json()
        job_types = {t["job_type"] for t in data["types"]}
        assert "meaning" in job_types
        assert "media" in job_types

    def test_filtered_by_source_id(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="err")
        _insert_job(db_session, 2, 2, 2, job_type="meaning", status="failed", error="err")
        db_session.commit()

        response = client.get("/api/queue/failed?source_id=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["types"]) == 1
        # only 1 candidate from source 1
        assert data["types"][0]["total_failed"] == 1


# ── cancel ───────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestCancelQueue:
    def test_cancel_by_job_id(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_job(db_session, 42, 1, 1, status="queued")
        db_session.commit()

        response = client.post(
            "/api/queue/cancel",
            json={"job_type": "meaning", "job_id": 42},
        )
        assert response.status_code == 200
        assert response.json() == {"cancelled": 1}

        # Verify job is gone via order endpoint
        order = client.get("/api/queue/order").json()
        assert order["queued"] == []

    def test_cancel_by_source_and_type(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="queued")
        _insert_job(db_session, 2, 2, 2, job_type="meaning", status="queued")
        db_session.commit()

        response = client.post(
            "/api/queue/cancel",
            json={"job_type": "meaning", "source_id": 1},
        )
        assert response.status_code == 200
        assert response.json() == {"cancelled": 1}

        # Source 2 job still there
        order = client.get("/api/queue/order").json()
        assert len(order["queued"]) == 1
        assert order["queued"][0]["source_id"] == 2

    def test_cancel_globally_by_type(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="queued")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="queued")
        _insert_job(db_session, 3, 3, 2, job_type="meaning", status="queued")
        db_session.commit()

        response = client.post(
            "/api/queue/cancel",
            json={"job_type": "meaning"},
        )
        assert response.status_code == 200
        assert response.json()["cancelled"] == 3

        order = client.get("/api/queue/order").json()
        assert order["queued"] == []

    def test_cancel_unknown_job_type_returns_zero(self, client: TestClient) -> None:
        response = client.post(
            "/api/queue/cancel",
            json={"job_type": "unknown_type"},
        )
        assert response.status_code == 200
        assert response.json() == {"cancelled": 0}

    def test_cancel_running_jobs_also_cancelled(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_job(db_session, 1, 1, 1, status="running", started_at="2026-01-01 01:00:00")
        db_session.commit()

        response = client.post(
            "/api/queue/cancel",
            json={"job_type": "meaning", "source_id": 1},
        )
        assert response.status_code == 200
        assert response.json() == {"cancelled": 1}


# ── retry ────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestRetryQueue:
    def test_retry_failed_by_type(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="timeout")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="failed", error="timeout")
        db_session.commit()

        response = client.post(
            "/api/queue/retry",
            json={"job_type": "meaning"},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 2}

        # Failed jobs should now be queued again
        order = client.get("/api/queue/order").json()
        assert len(order["queued"]) == 2

        failed = client.get("/api/queue/failed").json()
        assert failed["types"] == []

    def test_retry_by_error_text_filters_correctly(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Use two different sources so that delete_failed_by_source_and_type
        # only touches the source we want to retry (source 1 = timeout only).
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="timeout")
        _insert_job(db_session, 2, 2, 2, job_type="meaning", status="failed", error="connection refused")
        db_session.commit()

        response = client.post(
            "/api/queue/retry",
            json={"job_type": "meaning", "error_text": "timeout"},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 1}

        # Only the "timeout" job was retried; "connection refused" stays failed
        failed = client.get("/api/queue/failed").json()
        assert len(failed["types"]) == 1
        assert failed["types"][0]["groups"][0]["error_text"] == "connection refused"

    def test_retry_by_error_text_preserves_other_errors_in_same_source(
        self, client: TestClient, db_session: Session,
    ) -> None:
        """Retry with error_text must NOT delete failed jobs with a different error
        in the same source. Regression test for data-loss bug."""
        _insert_source(db_session, 1)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="timeout")
        _insert_job(db_session, 2, 2, 1, job_type="meaning", status="failed", error="timeout")
        _insert_job(db_session, 3, 3, 1, job_type="meaning", status="failed", error="rate limit")
        db_session.commit()

        response = client.post(
            "/api/queue/retry",
            json={"job_type": "meaning", "error_text": "timeout"},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 2}

        # "rate limit" job must still be in failed
        failed = client.get("/api/queue/failed").json()
        assert len(failed["types"]) == 1
        assert failed["types"][0]["groups"][0]["error_text"] == "rate limit"
        assert failed["types"][0]["total_failed"] == 1

        # The 2 "timeout" jobs should be re-queued
        order = client.get("/api/queue/order").json()
        assert len(order["queued"]) == 2

    def test_retry_unknown_job_type_returns_zero(self, client: TestClient) -> None:
        response = client.post(
            "/api/queue/retry",
            json={"job_type": "unknown_type"},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 0}

    def test_retry_when_no_failed_jobs_returns_zero(self, client: TestClient) -> None:
        response = client.post(
            "/api/queue/retry",
            json={"job_type": "meaning"},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 0}

    def test_retry_filtered_by_source_id(self, client: TestClient, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        _insert_job(db_session, 1, 1, 1, job_type="meaning", status="failed", error="err")
        _insert_job(db_session, 2, 2, 2, job_type="meaning", status="failed", error="err")
        db_session.commit()

        response = client.post(
            "/api/queue/retry",
            json={"job_type": "meaning", "source_id": 1},
        )
        assert response.status_code == 202
        assert response.json() == {"retried": 1}

        # Source 2 job still failed
        failed = client.get("/api/queue/failed").json()
        assert len(failed["types"]) == 1
        assert failed["types"][0]["total_failed"] == 1
