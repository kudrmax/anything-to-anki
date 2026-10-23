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


def _refuse_level_change(_self: object, _run: object) -> None:
    raise AssertionError(
        "A test started a level change; it runs on the app database, not the test's."
        " Replace Container._spawn_level_change and Container._level_change_run in the test."
    )


@pytest.fixture(autouse=True)
def _no_level_change_on_the_app_database(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.infrastructure.container import Container

    monkeypatch.setattr(Container, "_spawn_level_change", _refuse_level_change)


@pytest.fixture(autouse=True)
def _long_operations_run_in_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """An operation over sources runs in the request that starts it: on a thread of its own
    it would outlive the test's database."""
    from backend.infrastructure.container import Container

    monkeypatch.setattr(Container, "_spawn_long_operation", lambda _self, run: run())


@pytest.fixture(autouse=True)
def _no_long_operation_left_by_another_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry of operations and the index build are kept in memory for the process: a
    test whose background operation never ended would refuse every later level change."""
    from backend.infrastructure.api.running_operations import BOOTSTRAP_BUILDS
    from backend.infrastructure.api.source_operations import OPERATIONS

    monkeypatch.setattr(OPERATIONS, "_last", {})
    monkeypatch.setattr(BOOTSTRAP_BUILDS, "_running", None)
