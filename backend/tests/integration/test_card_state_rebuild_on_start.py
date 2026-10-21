"""The app computes the card state projection anew on every start, before any request."""
from __future__ import annotations

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_session_factory
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


def _revision() -> int:
    with get_session_factory()() as session:
        return int(session.execute(text("SELECT revision FROM projection_meta")).scalar_one())


def test_every_start_rebuilds_the_projection() -> None:
    with TestClient(app):
        first = _revision()
    with TestClient(app):
        assert _revision() == first + 1
