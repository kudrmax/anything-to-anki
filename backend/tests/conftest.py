import os
import tempfile
from collections.abc import Generator
from unittest.mock import patch

import pytest

# Tests get their own data folder. The app opens its database when imported and, on start,
# migrates it, cleans the enrichment cache and drops media files no card refers to — all in
# DATA_DIR, which otherwise is the real data of this copy of the app.
TEST_DATA_DIR = tempfile.mkdtemp(prefix="anything-to-anki-tests-")
os.environ["DATA_DIR"] = TEST_DATA_DIR
os.environ["MEDIA_ROOT"] = os.path.join(TEST_DATA_DIR, "media")
# The app serves the web build, when there is one, for every GET no API route takes; tests
# must see the API alone, whether or not the web app was built in this copy.
os.environ["FRONTEND_DIST"] = os.path.join(TEST_DATA_DIR, "no-web-build")

_ANKI_CONNECT_POST = "backend.infrastructure.adapters.anki_connect_connector.httpx.post"


def _refuse_real_anki(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("A test reached the real AnkiConnect; mock the connector call")


@pytest.fixture(autouse=True)
def _no_real_anki() -> Generator[None, None, None]:
    """Keeps tests away from the Anki running on this machine: it holds the user's real cards."""
    with patch(_ANKI_CONNECT_POST, side_effect=_refuse_real_anki):
        yield


class _RefusingRebuildLauncher:
    """Stands in for the app's background rebuild in every test: the pass would run on the
    app database whatever session factory the test gave the API."""

    def rebuild_all(self) -> None:
        raise AssertionError(
            "A test started the background rebuild of all sources; it runs on the app"
            " database, not the test's. Replace Container._rebuild_launcher in the test."
        )


@pytest.fixture(autouse=True)
def _no_rebuild_on_the_app_database(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.infrastructure.container import Container

    monkeypatch.setattr(Container, "_rebuild_launcher", lambda _self: _RefusingRebuildLauncher())
