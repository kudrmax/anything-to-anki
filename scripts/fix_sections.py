"""Give every phrase its earned section and rebuild the sources, once, after the update that
stored the sections (migration 0050). Run it with the app stopped: `make fix-sections`.

Reads the database from this copy's DATA_DIR. Migrates it first, frees the sources a crash
left busy, stamps the phrases that have no section, then rebuilds every source that can be
rebuilt (open cards are kept). Exits with 1 if a source could not be rebuilt.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import (
    create_session_factory,
    default_db_url,
    release_source_operations,
    run_alembic_migrations,
)

if TYPE_CHECKING:
    from backend.application.dto.fix_sections_dtos import FixSectionsReportDTO

FAILED_EXIT_CODE = 1


def fix_sections(db_url: str) -> FixSectionsReportDTO:
    run_alembic_migrations(db_url)
    session_factory = create_session_factory(db_url)
    release_source_operations(session_factory)
    container = Container(session_factory=session_factory)
    with session_factory() as session:
        return container.fix_sections_use_case(session).execute()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = fix_sections(default_db_url())
    print(  # noqa: T201
        f"phrases stamped: {report.phrases_stamped}\n"
        f"sources rebuilt: {report.sources_rebuilt}\n"
        f"failed sources: {report.failed or 'none'}",
    )
    return FAILED_EXIT_CODE if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
