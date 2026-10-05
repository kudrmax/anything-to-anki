from __future__ import annotations

import pytest
from backend.infrastructure.api.client_build import (
    CLIENT_BUILD_HEADER,
    STALE_CLIENT_HEADER,
    StaleClientMiddleware,
    bundle_name,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

BUILD = "index-XqoIC-cI.js"
INDEX_HTML = f'<script type="module" crossorigin src="/assets/{BUILD}"></script>'
FETCH = {"Sec-Fetch-Dest": "empty"}


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/sources")
    def sources() -> list[str]:
        return []

    app.add_middleware(StaleClientMiddleware, build=BUILD)
    return TestClient(app)


@pytest.mark.integration
def test_bundle_name_is_read_from_the_page() -> None:
    assert bundle_name(INDEX_HTML) == BUILD
    assert bundle_name("<html></html>") is None


@pytest.mark.integration
def test_current_client_is_left_alone() -> None:
    response = _client().get("/sources", headers={**FETCH, CLIENT_BUILD_HEADER: BUILD})

    assert STALE_CLIENT_HEADER not in response.headers
    assert "clear-site-data" not in response.headers


@pytest.mark.integration
def test_old_client_is_told_to_reload_and_loses_its_cache() -> None:
    response = _client().get("/sources", headers={**FETCH, CLIENT_BUILD_HEADER: "index-old.js"})

    assert response.headers[STALE_CLIENT_HEADER] == "1"
    assert response.headers["clear-site-data"] == '"cache"'


@pytest.mark.integration
def test_client_from_before_build_check_loses_its_cache() -> None:
    response = _client().get("/sources", headers=FETCH)

    assert response.headers["clear-site-data"] == '"cache"'


@pytest.mark.integration
def test_non_fetch_requests_are_not_checked() -> None:
    response = _client().get("/sources")

    assert "clear-site-data" not in response.headers
