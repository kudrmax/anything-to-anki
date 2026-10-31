"""Recent: the sources and collections the user worked with, the latest first."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime
from typing import Any

import pytest
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.sqla_recent_use_repository import SqlaRecentUseRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.projection_support import rebuild_projection
from tests.review_window_support import open_review
from tests.word_support import insert_word

pytestmark = pytest.mark.integration

PILOT, FINALE, OUTSIDE = 1, 2, 3


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    with made() as session:
        for source_id in (PILOT, FINALE, OUTSIDE):
            insert_source(session, source_id)
            insert_word(session, source_id, source_id=source_id, lemma=f"word{source_id}")
        session.commit()
        rebuild_projection(session)
    yield made
    engine.dispose()


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


# Any: the raw JSON of the API, as the test reads it.
def _recent(client: TestClient, query: str = "") -> list[dict[str, Any]]:
    response = client.get("/sources/recent", params={"query": query})
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


def _names(items: list[dict[str, Any]]) -> list[str]:
    return [
        item["source"]["title"] if item["kind"] == "source" else item["collection"]["name"]
        for item in items
    ]


def _collection(client: TestClient, name: str, parent_id: int | None = None) -> int:
    created: int = client.post(
        "/collections", json={"name": name, "parent_id": parent_id},
    ).json()["id"]
    return created


def _place(client: TestClient, source_id: int, collection_id: int) -> None:
    client.post("/sources/placements", json={"placements": [
        {"source_id": source_id, "collection_id": collection_id},
    ]})


def _used(factory: sessionmaker[Session], scope: SourceScope, day: int) -> None:
    with factory() as session:
        SqlaRecentUseRepository(session).mark([scope], datetime(2026, 1, day, tzinfo=UTC))
        session.commit()


def test_nothing_used_yet_leaves_recent_empty(client: TestClient) -> None:
    assert _recent(client) == []


def test_opening_a_review_puts_its_set_first(client: TestClient) -> None:
    show = _collection(client, "Show")
    _place(client, PILOT, show)

    open_review(client, str(show))
    open_review(client, f"source-{OUTSIDE}")

    items = _recent(client)
    assert [item["kind"] for item in items] == ["source", "collection"]
    assert items[0]["source"]["id"] == OUTSIDE
    assert items[1]["collection"]["id"] == show
    assert items[1]["collection"]["counts"]["total"] == 1


def test_reviewing_all_is_not_a_use(client: TestClient) -> None:
    open_review(client, "all")
    assert _recent(client) == []


def test_the_latest_use_wins(client: TestClient, factory: sessionmaker[Session]) -> None:
    _used(factory, SourceScope.source(PILOT), 1)
    _used(factory, SourceScope.source(FINALE), 2)
    _used(factory, SourceScope.source(PILOT), 3)
    _used(factory, SourceScope.source(FINALE), 1)

    assert [item["source"]["id"] for item in _recent(client)] == [PILOT, FINALE]


def test_a_subcollection_names_the_collections_above_it(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    books = _collection(client, "Books")
    dune = _collection(client, "Dune", books)
    _used(factory, SourceScope.collection(dune), 1)

    [item] = _recent(client)
    assert (item["collection"]["name"], item["path"]) == ("Dune", ["Books"])


def test_search_matches_titles_and_names(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    client.patch(f"/sources/{PILOT}/title", json={"title": "Dune, part one"})
    _used(factory, SourceScope.source(PILOT), 1)
    _used(factory, SourceScope.source(FINALE), 2)
    _used(factory, SourceScope.collection(_collection(client, "Dune")), 3)
    _used(factory, SourceScope.collection(_collection(client, "Arrival")), 4)

    assert _names(_recent(client, " dune ")) == ["Dune", "Dune, part one"]


def test_a_deleted_collection_and_source_leave_recent(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    show = _collection(client, "Show")
    _used(factory, SourceScope.collection(show), 1)
    _used(factory, SourceScope.source(OUTSIDE), 2)

    client.delete(f"/collections/{show}")
    client.delete(f"/sources/{OUTSIDE}")

    assert _recent(client) == []
