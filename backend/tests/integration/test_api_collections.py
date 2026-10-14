from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import SourceModel
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


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


TEXT_ANSWER = {"text.kind": "text"}
TEXT_REQUEST = {"text": "Hello world", "answers": TEXT_ANSWER}


@pytest.mark.integration
class TestCollectionsAPI:
    def test_tree_life_cycle_with_undo(self, client: TestClient, db_session: Session) -> None:
        friends = client.post("/collections", json={"name": "Friends"}).json()
        season = client.post(
            "/collections", json={"name": "Season 1", "parent_id": friends["id"]},
        ).json()
        db_session.add(SourceModel(title="Pilot", status="new", collection_id=season["id"]))
        db_session.commit()

        tree = client.get("/collections").json()
        assert tree["collections"][0]["children"][0]["counts"]["total"] == 1
        assert tree["all"]["pending"] == 1

        deleted = client.delete(f"/collections/{friends['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["evicted_source_count"] == 1
        assert client.get("/collections").json()["unsorted"]["total"] == 1

        assert client.post(f"/collections/{friends['id']}/restore").status_code == 200
        board = client.get("/sources/board", params={"scope": season["id"]}).json()
        assert board["title"] == "Friends / Season 1"
        assert [g["stage"] for g in board["groups"]] == ["preparing"]

    def test_duplicate_name_is_409_with_readable_text(self, client: TestClient) -> None:
        client.post("/collections", json={"name": "Worm"})
        response = client.post("/collections", json={"name": " worm "})
        assert response.status_code == 409
        assert response.json()["detail"] == 'Collection "worm" already exists here'

    def test_third_level_is_409(self, client: TestClient) -> None:
        top = client.post("/collections", json={"name": "A"}).json()
        sub = client.post("/collections", json={"name": "B", "parent_id": top["id"]}).json()
        third = client.post("/collections", json={"name": "C", "parent_id": sub["id"]})
        assert third.status_code == 409

    def test_move_answers_previous_place(self, client: TestClient) -> None:
        a = client.post("/collections", json={"name": "A"}).json()
        b = client.post("/collections", json={"name": "B"}).json()
        moved = client.post(
            f"/collections/{b['id']}/move", json={"parent_id": a["id"], "position": 0},
        )
        assert moved.json() == {"id": b["id"], "previous_parent_id": None, "previous_position": 1}

    def test_negative_move_position_is_rejected(self, client: TestClient) -> None:
        a = client.post("/collections", json={"name": "A"}).json()
        response = client.post(
            f"/collections/{a['id']}/move", json={"parent_id": None, "position": -1},
        )
        assert response.status_code == 422

    def test_unknown_collection_is_404_on_every_verb(self, client: TestClient) -> None:
        assert client.patch("/collections/999", json={"name": "X"}).status_code == 404
        assert client.post("/collections/999/move", json={"position": 0}).status_code == 404
        assert client.delete("/collections/999").status_code == 404
        assert client.post("/collections/999/restore").status_code == 404

    def test_board_unknown_collection_is_404(self, client: TestClient) -> None:
        assert client.get("/sources/board", params={"scope": "999"}).status_code == 404

    def test_board_bad_scope_is_400(self, client: TestClient) -> None:
        assert client.get("/sources/board", params={"scope": "nope"}).status_code == 400

    def test_placements_round_trip(self, client: TestClient, db_session: Session) -> None:
        ielts = client.post("/collections", json={"name": "IELTS"}).json()
        db_session.add(SourceModel(title="Essay", status="new"))
        db_session.commit()
        source_id = client.get("/sources").json()[0]["id"]
        placed = client.post("/sources/placements", json={
            "placements": [{"source_id": source_id, "collection_id": ielts["id"]}],
        }).json()
        assert placed == {"previous": [{"source_id": source_id, "collection_id": None}]}

    def test_delete_batch_removes_sources_once(self, client: TestClient) -> None:
        source_id = client.post("/sources/add", json=TEXT_REQUEST).json()["source_ids"][0]
        response = client.post(
            "/sources/delete-batch", json={"source_ids": [source_id, source_id]},
        )
        assert response.status_code == 200
        assert client.get("/sources").json() == []
