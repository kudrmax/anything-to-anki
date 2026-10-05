"""API of topic sources: creation, the queued AI step and its retry."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.topic_target import TopicTarget
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.integration

TOPIC_JOB = "topic_targets"
BLOCKED = "AI service error: Blocked country: RU. Turn on VPN."


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
    session = sessionmaker(bind=_db_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_db_engine: object) -> Generator[TestClient, None, None]:
    factory = sessionmaker(bind=_db_engine)

    def override_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_topic(client: TestClient, query: str = "negotiating a salary") -> int:
    response = client.post("/sources", json={"raw_text": query, "input_method": "topic_query"})
    assert response.status_code == 201
    source_id: int = response.json()["id"]
    return source_id


def _summary(client: TestClient, source_id: int) -> dict[str, object]:
    sources = client.get("/sources").json()
    found: dict[str, object] = next(s for s in sources if s["id"] == source_id)
    return found


def _fail_topic_job(session: Session, source_id: int, error: str) -> None:
    session.execute(
        text("UPDATE jobs SET status = 'failed', error = :error WHERE source_id = :sid"),
        {"error": error, "sid": source_id},
    )
    session.commit()


def test_new_topic_awaits_generation(client: TestClient) -> None:
    source_id = _create_topic(client)

    summary = _summary(client, source_id)
    assert summary["content_type"] == "topic"
    assert summary["title"] == "negotiating a salary"
    assert summary["awaiting_generation"] is True
    assert summary["generation_status"] is None


def test_generation_is_queued_once(client: TestClient) -> None:
    source_id = _create_topic(client)

    first = client.post(f"/sources/{source_id}/topic-targets/generate")
    second = client.post(f"/sources/{source_id}/topic-targets/generate")

    assert first.status_code == 202
    assert second.status_code == 409
    assert _summary(client, source_id)["generation_status"] == "queued"
    queue = client.get(f"/api/queue?source_id={source_id}").json()
    assert queue["counts"] == [
        {"job_type": TOPIC_JOB, "queued": 1, "running": 0, "failed": 0},
    ]


def test_generation_is_only_for_topics(client: TestClient) -> None:
    created = client.post(
        "/sources", json={"raw_text": "Some text.", "input_method": "text_pasted"},
    )
    response = client.post(f"/sources/{created.json()['id']}/topic-targets/generate")
    assert response.status_code == 400


def test_topic_with_targets_no_longer_awaits_generation(
    client: TestClient, db_session: Session,
) -> None:
    source_id = _create_topic(client)
    SqlaTopicTargetRepository(db_session).create_batch([
        TopicTarget(source_id=source_id, position=0, phrase="negotiate",
                    example="We **negotiate** the offer."),
    ])
    db_session.commit()

    assert _summary(client, source_id)["awaiting_generation"] is False
    response = client.post(f"/sources/{source_id}/topic-targets/generate")
    assert response.status_code == 409


def test_topic_cannot_be_processed_before_generation(client: TestClient) -> None:
    source_id = _create_topic(client)
    response = client.post(f"/sources/{source_id}/process")
    assert response.status_code == 409


def test_failed_generation_is_shown_and_can_be_retried(
    client: TestClient, db_session: Session,
) -> None:
    source_id = _create_topic(client)
    client.post(f"/sources/{source_id}/topic-targets/generate")
    _fail_topic_job(db_session, source_id, BLOCKED)

    summary = _summary(client, source_id)
    assert summary["generation_status"] == "failed"
    assert summary["generation_error"] == BLOCKED

    response = client.post(
        "/api/queue/retry",
        json={"job_type": TOPIC_JOB, "source_id": source_id, "error_text": BLOCKED},
    )
    assert response.json() == {"affected": 1}
    assert _summary(client, source_id)["generation_status"] == "queued"


def test_retry_by_error_text_keeps_other_failures(
    client: TestClient, db_session: Session,
) -> None:
    blocked_id = _create_topic(client, "salary")
    other_id = _create_topic(client, "medicine")
    for source_id in (blocked_id, other_id):
        client.post(f"/sources/{source_id}/topic-targets/generate")
    _fail_topic_job(db_session, blocked_id, BLOCKED)
    _fail_topic_job(db_session, other_id, "timeout")

    response = client.post(
        "/api/queue/retry", json={"job_type": TOPIC_JOB, "error_text": BLOCKED},
    )

    assert response.json() == {"affected": 1}
    assert _summary(client, blocked_id)["generation_status"] == "queued"
    assert _summary(client, other_id)["generation_status"] == "failed"


def test_generation_can_be_cancelled(client: TestClient) -> None:
    source_id = _create_topic(client)
    client.post(f"/sources/{source_id}/topic-targets/generate")

    response = client.post(
        "/api/queue/cancel", json={"job_type": TOPIC_JOB, "source_id": source_id},
    )

    assert response.json() == {"affected": 1}
    assert _summary(client, source_id)["generation_status"] is None
