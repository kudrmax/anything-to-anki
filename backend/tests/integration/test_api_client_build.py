from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.api.client_build import (
    CLIENT_BUILD_HEADER,
    STALE_CLIENT_HEADER,
    StaleClientMiddleware,
    bundle_name,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path

BUILD = "index-XqoIC-cI.js"
FETCH = {"Sec-Fetch-Dest": "empty"}


def _page(build: str) -> str:
    return f'<script type="module" crossorigin src="/assets/{build}"></script>'


def _client(dist: Path) -> TestClient:
    (dist / "index.html").write_text(_page(BUILD))
    app = FastAPI()

    @app.get("/sources")
    def sources() -> list[str]:
        return []

    app.add_middleware(StaleClientMiddleware, dist=dist)
    return TestClient(app)


@pytest.mark.integration
def test_bundle_name_is_read_from_the_page() -> None:
    assert bundle_name(_page(BUILD)) == BUILD
    assert bundle_name("<html></html>") is None


@pytest.mark.integration
def test_current_client_is_left_alone(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/sources", headers={**FETCH, CLIENT_BUILD_HEADER: BUILD})

    assert STALE_CLIENT_HEADER not in response.headers
    assert "clear-site-data" not in response.headers


@pytest.mark.integration
def test_old_client_is_told_to_reload_and_loses_its_cache(tmp_path: Path) -> None:
    stale = {**FETCH, CLIENT_BUILD_HEADER: "index-old.js"}
    response = _client(tmp_path).get("/sources", headers=stale)

    assert response.headers[STALE_CLIENT_HEADER] == "1"
    assert response.headers["clear-site-data"] == '"cache"'


@pytest.mark.integration
def test_client_from_before_build_check_loses_its_cache(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/sources", headers=FETCH)

    assert response.headers["clear-site-data"] == '"cache"'


@pytest.mark.integration
def test_non_fetch_requests_are_not_checked(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/sources")

    assert "clear-site-data" not in response.headers


@pytest.mark.integration
def test_page_of_a_build_made_while_the_server_runs_is_current(tmp_path: Path) -> None:
    client = _client(tmp_path)
    (tmp_path / "index.html").write_text(_page("index-new.js"))

    fresh = client.get("/sources", headers={**FETCH, CLIENT_BUILD_HEADER: "index-new.js"})
    old = client.get("/sources", headers={**FETCH, CLIENT_BUILD_HEADER: BUILD})

    assert STALE_CLIENT_HEADER not in fresh.headers
    assert old.headers[STALE_CLIENT_HEADER] == "1"


@pytest.mark.integration
def test_nothing_is_checked_without_a_build(tmp_path: Path) -> None:
    client = _client(tmp_path)
    (tmp_path / "index.html").write_text("<html></html>")

    response = client.get("/sources", headers=FETCH)

    assert "clear-site-data" not in response.headers
