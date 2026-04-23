import os
from collections.abc import Generator

import pytest


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
