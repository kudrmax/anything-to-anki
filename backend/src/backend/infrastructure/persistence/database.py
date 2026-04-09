from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.domain.value_objects.source_status import SourceStatus

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def default_db_url() -> str:
    data_dir = os.getenv("DATA_DIR", ".")
    return f"sqlite:///{data_dir}/app.db"


def run_alembic_migrations(db_url: str) -> None:
    """Run all pending Alembic migrations up to head."""
    from pathlib import Path as _Path

    from alembic import command
    from alembic.config import Config

    # alembic/ lives at backend/src/backend/alembic/ — find it relative to this file.
    # Works both in development (editable install) and in Docker (installed package).
    alembic_dir = _Path(__file__).parent.parent.parent / "alembic"
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


def create_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""
    engine = create_engine(db_url or default_db_url(), connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine)


def create_tables(session_factory: sessionmaker[Session]) -> None:
    """Create all tables from model metadata."""
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)


def reset_stuck_processing(session_factory: sessionmaker[Session]) -> None:
    """Reset sources stuck in PROCESSING status back to NEW (after crash recovery)."""
    from backend.infrastructure.persistence.models import SourceModel

    session = session_factory()
    try:
        session.execute(
            update(SourceModel)
            .where(SourceModel.status == SourceStatus.PROCESSING.value)
            .values(status=SourceStatus.NEW.value, processing_stage=None)
        )
        session.commit()
    finally:
        session.close()


def reconcile_media_files(session_factory: sessionmaker[Session], media_root: str) -> None:
    """Remove orphan media files/directories without corresponding DB records.

    Two-phase scan on startup:
    Phase 1: for each source_id directory in media_root, verify source exists in DB.
             If not, remove the directory entirely.
    Phase 2: for each `{candidate_id}_{kind}.{ext}` file in a valid source directory,
             verify the candidate exists in DB. If not, remove the file.

    Orphan DB paths (file missing but DB still has path) are handled by the
    runtime lazy reconciler, not here.
    """
    import re
    import shutil

    from backend.infrastructure.persistence.sqla_candidate_repository import (
        SqlaCandidateRepository,
    )
    from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

    if not os.path.isdir(media_root):
        return

    numeric_dirs = [
        e for e in os.listdir(media_root)
        if e.isdigit() and os.path.isdir(os.path.join(media_root, e))
    ]
    if not numeric_dirs:
        return

    session = session_factory()
    try:
        source_repo = SqlaSourceRepository(session)
        candidate_repo = SqlaCandidateRepository(session)
        file_pattern = re.compile(r"^(\d+)_(screenshot|audio)\.")

        for entry in numeric_dirs:
            source_id = int(entry)
            source_dir = os.path.join(media_root, entry)

            if source_repo.get_by_id(source_id) is None:
                shutil.rmtree(source_dir, ignore_errors=True)
                logger.info("Reconcile: removed orphan media dir %s", source_dir)
                continue

            # Phase 2: check each file in the valid source directory
            for fname in os.listdir(source_dir):
                m = file_pattern.match(fname)
                if not m:
                    continue  # unknown file, leave it
                candidate_id = int(m.group(1))
                if candidate_repo.get_by_id(candidate_id) is None:
                    fpath = os.path.join(source_dir, fname)
                    try:
                        os.remove(fpath)
                        logger.info("Reconcile: removed orphan media file %s", fpath)
                    except OSError:
                        logger.warning(
                            "Reconcile: failed to remove orphan file %s", fpath, exc_info=True,
                        )
    finally:
        session.close()
