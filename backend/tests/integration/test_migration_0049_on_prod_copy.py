"""Migration 0049 on a copy of the real database: every assert of design §4.1.

Runs only on request, because it reads the prod copy's database (read-only; the
migration runs on a copy in a temporary directory):

    MIGRATION_PROD_COPY=1 DICTIONARIES_DIR=... .venv/bin/python -m pytest \\
        backend/tests/integration/test_migration_0049_on_prod_copy.py -q -s

`MIGRATION_PROD_DB` points at another database file if needed. The database must be
at revision 0048. The counts by mapping row, the listed released rows and exceptions, and
the per-source progress before and after are printed for the commit that ran this test.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database

from tests.migration_0049_checks import check_upgraded, read_before

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("MIGRATION_PROD_COPY") != "1",
        reason="reads the prod database; set MIGRATION_PROD_COPY=1 to run",
    ),
]

DEFAULT_PROD_DB = Path.home() / "projects" / "anything-to-anki-prod" / "data" / "app.db"
REVISION_BEFORE = "0048"
REVISION_UNDER_TEST = "0049"
DROPPED_DECISION_PREFIX = "0049: merge dropped"


def _copy(source: Path, target: Path) -> None:
    original = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(target)
        try:
            original.backup(copy)
        finally:
            copy.close()
    finally:
        original.close()


def _config(db_path: Path) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_prod_copy_meets_every_section_4_1_assert(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    db_path = tmp_path / "app.db"
    _copy(Path(os.environ.get("MIGRATION_PROD_DB", str(DEFAULT_PROD_DB))), db_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            REVISION_BEFORE
        )
        before = read_before(conn)

    caplog.set_level(logging.WARNING)
    started = datetime.now(tz=UTC).replace(tzinfo=None)
    command.upgrade(_config(db_path), REVISION_UNDER_TEST)
    finished = datetime.now(tz=UTC).replace(tzinfo=None)
    dropped = [
        int(record.args[1])  # type: ignore[index]
        for record in caplog.records if record.msg.startswith(DROPPED_DECISION_PREFIX)
    ]

    with sqlite3.connect(db_path) as conn:
        report = check_upgraded(conn, before, started, finished, dropped)
    # The numbers go into the commit that ran this test.
    print("counts by §4 mapping row and reason:")  # noqa: T201
    for reason, count in sorted(report.counts.items()):
        print(f"  {reason}: {count}")  # noqa: T201
    for reason, ids in sorted(report.listed.items()):
        if not reason.startswith("old "):
            print(f"listed — {reason}: {ids}")  # noqa: T201
    for source_id in sorted(set(before.progress) | set(report.progress_after)):
        print(  # noqa: T201
            f"source {source_id}: before {before.progress.get(source_id)}"
            f" after {report.progress_after.get(source_id)}",
        )

    with pytest.raises(NotImplementedError):
        command.downgrade(_config(db_path), REVISION_BEFORE)
