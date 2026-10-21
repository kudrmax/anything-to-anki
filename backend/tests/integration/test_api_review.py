"""The review screen of a set of sources: one source, a collection or all of them, through
one endpoint that takes the set's scope token."""
from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.projection_support import rebuild_projection
from tests.review_support import on_review
from tests.review_window_support import open_review, review_list
from tests.word_support import insert_word

pytestmark = pytest.mark.integration

PILOT, FINALE, OUTSIDE = 1, 2, 3


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        for source_id in (PILOT, FINALE, OUTSIDE):
            insert_source(session, source_id)
        insert_word(session, 1, source_id=PILOT, lemma="glare")
        insert_word(session, 2, source_id=FINALE, lemma="relentless")
        insert_word(session, 3, source_id=OUTSIDE, lemma="lizard")
        session.commit()
        rebuild_projection(session)

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _show(client: TestClient) -> str:
    show = client.post("/collections", json={"name": "Show"}).json()
    client.post("/sources/placements", json={"placements": [
        {"source_id": PILOT, "collection_id": show["id"]},
        {"source_id": FINALE, "collection_id": show["id"]},
    ]})
    return str(show["id"])


def test_a_collection_reviews_the_cards_of_its_sources(client: TestClient) -> None:
    scope = _show(client)
    header = open_review(client, scope)["header"]
    assert (header["scope"], header["title"], header["busy"]) == (scope, "Show", False)
    cards = review_list(client, scope)
    assert sorted(c["source"]["id"] for c in cards) == [PILOT, FINALE]
    assert sorted(c["lemma"] for c in cards) == ["glare", "relentless"]


def test_a_source_is_a_set_of_one(client: TestClient) -> None:
    assert open_review(client, f"source-{PILOT}")["header"]["scope"] == f"source-{PILOT}"
    assert [c["lemma"] for c in review_list(client, f"source-{PILOT}")] == ["glare"]


def test_all_sources_is_a_set(client: TestClient) -> None:
    header = open_review(client, "all")["header"]
    assert (header["scope"], header["title"]) == ("all", "All sources")
    assert len(review_list(client, "all")) == 3


def test_review_scope_errors(client: TestClient) -> None:
    assert client.post("/api/review", json={"scope": "unsorted"}).status_code == 400
    assert client.post("/api/review", json={"scope": "garbage"}).status_code == 400
    assert client.post("/api/review", json={"scope": "source-99"}).status_code == 404
    assert client.post("/api/review", json={"scope": "99"}).status_code == 404
    assert client.get("/api/review/documents", params={"scope": "unsorted"}).status_code == 400
    assert client.get("/api/review/documents", params={"scope": "source-99"}).status_code == 404


def test_the_whole_list_read_is_gone(client: TestClient) -> None:
    assert client.get("/api/review", params={"scope": "all"}).status_code == 405
    assert client.get("/api/review/candidates", params={"scope": "all"}).status_code == 404


def test_old_source_detail_is_gone(client: TestClient) -> None:
    assert client.get(f"/sources/{PILOT}").status_code == 405
    assert client.get(f"/sources/{PILOT}/candidates").status_code == 404
    assert client.get(f"/sources/{PILOT}/document").status_code == 404


def test_review_page_path_is_left_to_the_web_app(client: TestClient) -> None:
    assert client.get("/review").status_code == 404
    assert client.post("/api/review", json={"scope": "all"}).status_code == 200


def test_sources_without_a_document_have_no_text(client: TestClient) -> None:
    assert client.get("/api/review/documents", params={"scope": _show(client)}).json() == []


def test_download_video_of_a_set_without_links_is_400(client: TestClient) -> None:
    scope = _show(client)
    assert on_review(
        client, "POST", "/api/review/download-video", params={"scope": scope},
    ).status_code == 400
    assert on_review(
        client, "POST", "/api/review/download-video", params={"scope": "unsorted"},
    ).status_code == 400
    assert client.post(f"/sources/{PILOT}/download-video").status_code == 404
