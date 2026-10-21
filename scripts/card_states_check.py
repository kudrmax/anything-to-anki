"""Compare the stored projection of card state with the rows computed live, the way the
review computes them today: `make card-states-check [DB=…]`.

Reads this copy's database (DATA_DIR) or the one given, opened query-only in one read
transaction, so a running app does not shift it midway. Prints every differing row and exits
with 1 if there is one. Never writes and never migrates.

An Anki timer of 30 days that passed since the last rebuild, write or time tick shows as a
difference until the worker's next time tick (once a minute) writes it.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from backend.application.utils.card_state_differences import differences
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import (
    SQLITE_FILE_URL_PREFIX,
    default_db_url,
    open_query_only,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    import sqlite3

DIFFERENT_EXIT_CODE = 1


def _read_only_session_factory(path: str) -> sessionmaker[Session]:
    def connect() -> sqlite3.Connection:
        if not Path(path).is_file():
            raise SystemExit(f"No database at {path}")
        connection = open_query_only(path)
        connection.isolation_level = None
        return connection

    return sessionmaker(bind=create_engine("sqlite://", creator=connect))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="SQLite file; this copy's database by default")
    args = parser.parse_args()
    path = args.db or default_db_url().removeprefix(SQLITE_FILE_URL_PREFIX)

    started = time.perf_counter()
    session_factory = _read_only_session_factory(path)
    container = Container(session_factory=session_factory)
    with session_factory() as session:
        session.connection().exec_driver_sql("BEGIN")
        stored = container.card_state_projector(session).stored()
        live = container.live_card_states(session).compute()
        session.rollback()
    found = differences(stored, live)
    for difference in found:
        print(difference)  # noqa: T201
    print(  # noqa: T201
        f"{path}: cards stored={sum(not c.removed for c in stored.cards)}"
        f" live={len(live.cards)}, words={len(live.words)},"
        f" phrase words={len(live.phrase_words)}, revision={stored.revision};"
        f" differences={len(found)} ({time.perf_counter() - started:.1f} s)",
    )
    return DIFFERENT_EXIT_CODE if found else 0


if __name__ == "__main__":
    sys.exit(main())
