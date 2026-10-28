from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.settings_card_layout_repository import (
    CARD_LAYOUT_SETTING,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


class _NoChanges:
    def record(self, change: object) -> None:
        pass


@pytest.fixture()
def test_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def client(test_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: test_session_factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def first_column(view: dict[str, object]) -> list[dict[str, object]]:
    layout = view["layout"]
    assert isinstance(layout, dict)
    rows: list[dict[str, object]] = layout["columns"][0]["rows"]
    return rows


def style_of(view: dict[str, object], element: str) -> dict[str, object]:
    layout = view["layout"]
    assert isinstance(layout, dict)
    return next(s["style"] for s in layout["styles"] if s["element"] == element)


@pytest.mark.integration
class TestCardLayoutAPI:
    def test_default(self, client: TestClient) -> None:
        view = client.get("/api/card-layout").json()
        assert view["hidden"] == []
        assert first_column(view)[:2] == [
            {"kind": "blocks", "elements": ["target"]}, {"kind": "divider"},
        ]
        assert {"element": "picture", "kind": "media", "can_hide": True} in view["elements"]
        always_shown = {"element": "picture_choice", "kind": "media", "can_hide": False}
        assert always_shown in view["elements"]
        assert view["can_add_column"] is True

    def test_edit_is_kept(self, client: TestClient) -> None:
        edited = client.post(
            "/api/card-layout/edits", json={"kind": "hide_block", "element": "target"},
        ).json()
        assert edited["hidden"] == ["target"]
        assert client.get("/api/card-layout").json() == edited

    def test_restyle_changes_only_what_is_given(self, client: TestClient) -> None:
        view = client.post(
            "/api/card-layout/edits",
            json={"kind": "restyle_block", "element": "translation", "tone": "muted"},
        ).json()
        assert style_of(view, "translation") == {
            "size": "xl", "tone": "muted", "bold": True, "align": "start", "valign": "baseline",
            "space_top": "none", "space_right": "none",
            "space_bottom": "none", "space_left": "none",
        }

    def test_restyle_space_on_each_side(self, client: TestClient) -> None:
        view = client.post(
            "/api/card-layout/edits",
            json={
                "kind": "restyle_block", "element": "translation",
                "space_left": "l", "space_bottom": "s",
            },
        ).json()
        style = style_of(view, "translation")
        assert [style[f"space_{side}"] for side in ("top", "right", "bottom", "left")] == [
            "none", "none", "s", "l",
        ]

    def test_restyle_vertical_position(self, client: TestClient) -> None:
        view = client.post(
            "/api/card-layout/edits",
            json={"kind": "restyle_block", "element": "tts", "valign": "bottom"},
        ).json()
        assert style_of(view, "tts")["valign"] == "bottom"

    def test_reset(self, client: TestClient) -> None:
        default = client.get("/api/card-layout").json()
        client.post("/api/card-layout/edits", json={"kind": "add_column"})
        reset = client.post("/api/card-layout/edits", json={"kind": "reset"}).json()
        assert reset == default

    def test_edit_outside_the_layout(self, client: TestClient) -> None:
        response = client.post(
            "/api/card-layout/edits", json={"kind": "remove_divider", "column": 0, "row": 0},
        )
        assert response.status_code == 400

    def test_element_added_later_comes_hidden(
        self, client: TestClient, test_session_factory: sessionmaker[Session],
    ) -> None:
        stored = (
            '{"columns": [{"width": "normal", "rows": ['
            '{"kind": "blocks", "elements": ["target", "gone"]}]}],'
            ' "styles": [{"element": "target", "style":'
            ' {"size": "s", "tone": "muted", "bold": false, "align": "start"}}]}'
        )
        with test_session_factory() as session:
            SqlaSettingsRepository(session, _NoChanges()).set(CARD_LAYOUT_SETTING, stored)
            session.commit()
        view = client.get("/api/card-layout").json()
        # The picture choice is always on the card: a saved layout without it gets it back.
        assert first_column(view) == [
            {"kind": "blocks", "elements": ["target"]},
            {"kind": "blocks", "elements": ["picture_choice"]},
        ]
        assert style_of(view, "target")["size"] == "s"
        assert style_of(view, "target")["valign"] == "baseline"
        assert style_of(view, "target")["space_left"] == "none"
        assert "translation" in view["hidden"]
