from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.api.app import INDEX_CACHE_CONTROL, index_response

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
def test_index_page_is_rechecked_on_every_open(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html>")

    response = index_response(tmp_path)

    assert response.headers["cache-control"] == INDEX_CACHE_CONTROL
