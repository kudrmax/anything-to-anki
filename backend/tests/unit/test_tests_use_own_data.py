"""The app under test never reaches this copy's real data folder."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from backend.infrastructure.api.dependencies import get_session_factory

from tests.conftest import TEST_DATA_DIR

pytestmark = pytest.mark.unit

REPO_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def test_app_database_lives_in_the_tests_data_folder() -> None:
    database = Path(str(get_session_factory().kw["bind"].url.database)).resolve()
    assert database.is_relative_to(Path(TEST_DATA_DIR).resolve())
    assert not database.is_relative_to(REPO_DATA_DIR)


def test_media_root_is_not_the_real_one() -> None:
    assert not Path(os.environ["MEDIA_ROOT"]).resolve().is_relative_to(REPO_DATA_DIR)
