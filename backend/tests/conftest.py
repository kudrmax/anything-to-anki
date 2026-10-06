import os
from collections.abc import Generator
from unittest.mock import patch

import pytest

_ANKI_CONNECT_POST = "backend.infrastructure.adapters.anki_connect_connector.httpx.post"


def _refuse_real_anki(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("A test reached the real AnkiConnect; mock the connector call")


@pytest.fixture(autouse=True)
def _no_real_anki() -> Generator[None, None, None]:
    """Keeps tests away from the Anki running on this machine: it holds the user's real cards."""
    with patch(_ANKI_CONNECT_POST, side_effect=_refuse_real_anki):
        yield


@pytest.fixture(autouse=True)
def _cleanup_stale_db() -> Generator[None, None, None]:
    """Remove stale app.db before each test.

    TestClient(app) triggers lifespan which runs alembic on the file-based DB
    pointed to by default_db_url() (./app.db). If a previous test already
    created that file and populated it with tables via Base.metadata.create_all,
    the next test's alembic run hits 'table already exists'. Cleaning up
    before each test prevents cross-test pollution.
    """
    for candidate in ("app.db", "backend/app.db"):
        if os.path.exists(candidate):
            os.remove(candidate)
    yield
    for candidate in ("app.db", "backend/app.db"):
        if os.path.exists(candidate):
            os.remove(candidate)
