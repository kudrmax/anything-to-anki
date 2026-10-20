"""The user's one order of sources: stored in the settings, the same for every set."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel, StoredCandidateModel
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


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


def _day(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def _seed(client: TestClient, db_session: Session) -> int:
    """Four new sources added on days 1..4, three of them in a collection; titles and marks
    run in other orders."""
    collection = client.post("/collections", json={"name": "Show"}).json()["id"]
    rows = [
        (1, "banana", collection, _day(10, 9)),
        (2, "Apple", collection, None),
        (3, "cherry", collection, _day(10, 11)),
        (4, "apple", None, None),
    ]
    for source_id, title, collection_id, studied in rows:
        db_session.add(SourceModel(
            id=source_id, title=title, status="new", collection_id=collection_id,
            created_at=_day(source_id),
        ))
        if studied is not None:
            db_session.add(StoredCandidateModel(
                source_id=source_id, lemma=f"word{source_id}", pos="NOUN", zipf_frequency=3.0,
                is_sweet_spot=False, occurrences=1, status="pending", studied_at=studied,
            ))
    db_session.commit()
    return int(collection)


def _board(client: TestClient, scope: str = "all") -> list[tuple[str | None, list[str]]]:
    groups = client.get("/sources/board", params={"scope": scope}).json()["groups"]
    return [(g["stage"], [s["title"] for s in g["sources"]]) for g in groups]


def test_the_default_order_is_by_stage_newest_added_first(
    client: TestClient, db_session: Session,
) -> None:
    settings = client.get("/api/settings").json()
    assert (settings["source_grouping"], settings["source_sort"]) == ("stage", "added")
    _seed(client, db_session)
    assert _board(client) == [("preparing", ["apple", "cherry", "Apple", "banana"])]


def test_one_choice_orders_every_set(client: TestClient, db_session: Session) -> None:
    collection = _seed(client, db_session)

    response = client.patch("/api/settings", json={"source_sort": "name"})

    assert response.status_code == 200
    assert response.json()["source_sort"] == "name"
    assert _board(client) == [("preparing", ["Apple", "apple", "banana", "cherry"])]
    assert _board(client, str(collection)) == [("preparing", ["Apple", "banana", "cherry"])]


def test_last_studied_puts_the_never_marked_last(
    client: TestClient, db_session: Session,
) -> None:
    _seed(client, db_session)
    client.patch("/api/settings", json={"source_sort": "last_studied"})
    assert _board(client) == [("preparing", ["cherry", "banana", "apple", "Apple"])]


def test_the_direction_reverses_the_sort_everywhere(
    client: TestClient, db_session: Session,
) -> None:
    collection = _seed(client, db_session)
    assert client.get("/api/settings").json()["source_sort_direction"] == "forward"

    client.patch("/api/settings", json={"source_sort": "name", "source_sort_direction": "reverse"})

    assert _board(client) == [("preparing", ["cherry", "banana", "apple", "Apple"])]
    assert _board(client, str(collection)) == [("preparing", ["cherry", "banana", "Apple"])]


def test_ungrouped_is_one_group_with_no_stage(client: TestClient, db_session: Session) -> None:
    _seed(client, db_session)
    client.patch("/api/settings", json={"source_grouping": "none"})
    assert _board(client) == [(None, ["apple", "cherry", "Apple", "banana"])]


@pytest.mark.parametrize(
    "change",
    [{"source_grouping": "collection"}, {"source_sort": "size"}, {"source_sort_direction": "up"}],
)
def test_an_unknown_option_is_rejected(client: TestClient, change: dict[str, str]) -> None:
    assert client.patch("/api/settings", json=change).status_code == 422
    settings = client.get("/api/settings").json()
    assert (settings["source_grouping"], settings["source_sort"]) == ("stage", "added")
