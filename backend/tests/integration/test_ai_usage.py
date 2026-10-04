"""AI usage history: migration, repository, recorder and the /api/usage endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.session_ai_usage_recorder import SessionAIUsageRecorder
from backend.infrastructure.persistence.sqla_ai_usage_repository import SqlaAIUsageRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration


def _record(at: datetime, feature: AIFeature = AIFeature.MEANING_BATCH) -> AIUsageRecord:
    return AIUsageRecord(
        feature=feature,
        model="claude-x",
        usage=TokenUsage(input_tokens=1, output_tokens=2, cache_read_tokens=3,
                         cache_creation_tokens=4),
        item_count=5,
        duration_ms=600,
        succeeded=True,
        created_at=at,
    )


@pytest.fixture()
def engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


def test_migration_creates_a_table_the_repository_can_use(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(database.__file__).parent.parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    migrated = create_engine(db_url)
    at = datetime(2026, 10, 4, 12, tzinfo=UTC)
    with Session(migrated) as session:
        SqlaAIUsageRepository(session).add(_record(at))
        session.commit()
        [stored] = SqlaAIUsageRepository(session).list_between(None, at + timedelta(seconds=1))
    migrated.dispose()

    assert stored.usage == TokenUsage(1, 2, 3, 4)
    assert stored.created_at == at


def test_repository_round_trip_and_bounds(session_factory: sessionmaker[Session]) -> None:
    day = datetime(2026, 10, 4, tzinfo=UTC)
    with session_factory() as session:
        repo = SqlaAIUsageRepository(session)
        for hours in (1, 5, 9):
            repo.add(_record(day + timedelta(hours=hours)))

        between = repo.list_between(day + timedelta(hours=5), day + timedelta(hours=9))
        everything = repo.list_between(None, day + timedelta(days=1))

        assert [r.created_at.hour for r in between] == [5]
        assert [r.created_at.hour for r in everything] == [1, 5, 9]
        assert everything[0].feature is AIFeature.MEANING_BATCH
        assert everything[0].item_count == 5
        assert repo.first_recorded_at() == day + timedelta(hours=1)


def test_empty_history_has_no_start(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        assert SqlaAIUsageRepository(session).first_recorded_at() is None


def test_recorder_survives_the_callers_rollback(session_factory: sessionmaker[Session]) -> None:
    at = datetime(2026, 10, 4, 12, tzinfo=UTC)
    caller = session_factory()
    SessionAIUsageRecorder(session_factory).record(_record(at))
    caller.rollback()
    caller.close()

    with session_factory() as session:
        assert len(SqlaAIUsageRepository(session).list_between(None, at + timedelta(days=1))) == 1


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_usage_endpoint_returns_stats(
    client: TestClient, session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(tz=UTC)
    with session_factory() as session:
        SqlaAIUsageRepository(session).add(_record(now - timedelta(minutes=1)))
        SqlaAIUsageRepository(session).add(
            _record(now - timedelta(minutes=1), AIFeature.PHRASE_POLISH),
        )
        session.commit()

    response = client.get("/api/usage", params={"period": "7d", "tz": "Europe/Moscow"})

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "7d"
    assert body["bucket_size"] == "day"
    assert len(body["buckets"]) == 7
    assert body["totals"]["tokens"]["total"] == 20
    assert body["totals"]["requests"] == 2
    assert {f["feature"] for f in body["features"]} == {"meaning_batch", "phrase_polish"}


def test_usage_endpoint_defaults_to_30_days(client: TestClient) -> None:
    body = client.get("/api/usage").json()
    assert body["period"] == "30d"
    assert body["tracking_since"] is None


def test_usage_endpoint_rejects_unknown_timezone(client: TestClient) -> None:
    response = client.get("/api/usage", params={"tz": "Mars/Olympus"})
    assert response.status_code == 400


def test_usage_endpoint_rejects_unknown_period(client: TestClient) -> None:
    response = client.get("/api/usage", params={"period": "year"})
    assert response.status_code == 422
