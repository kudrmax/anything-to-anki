"""Свежая копия проекта должна подниматься без ручной подготовки каталогов.

`data/` лежит в .gitignore, поэтому в только что склонированном репозитории её
нет. SQLite не создаёт недостающие директории сам и падает с
`unable to open database file` — приложение не стартует, тесты не проходят.
Каталог под файл БД обязан создаваться кодом.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.infrastructure.persistence.database import create_session_factory


@pytest.mark.unit
def test_creates_missing_directory_for_sqlite_file(tmp_path: Path) -> None:
    """Каталог под файл БД создаётся, если его ещё нет."""
    missing_dir = tmp_path / "data"
    assert not missing_dir.exists()

    session_factory = create_session_factory(f"sqlite:///{missing_dir}/app.db")
    session = session_factory()
    try:
        assert missing_dir.is_dir()
    finally:
        session.close()


@pytest.mark.unit
def test_in_memory_url_needs_no_directory() -> None:
    """In-memory БД не должна приводить к созданию каких-либо каталогов."""
    session_factory = create_session_factory("sqlite:///:memory:")
    session = session_factory()
    try:
        assert not Path(":memory:").exists()
    finally:
        session.close()
