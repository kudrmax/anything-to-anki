from __future__ import annotations

import logging
import os
from functools import cache
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

if TYPE_CHECKING:
    import sqlite3

    from alembic.config import Config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


SQLITE_FILE_URL_PREFIX = "sqlite:///"
SQLITE_IN_MEMORY_PATH = ":memory:"
SQLITE_BUSY_TIMEOUT_MS = 30_000


def default_db_url() -> str:
    data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
    return f"sqlite:///{data_dir}/app.db"


def _sqlite_file(db_url: str) -> str | None:
    """The path of a file-based SQLite DB; None for any other URL."""
    if not db_url.startswith(SQLITE_FILE_URL_PREFIX):
        return None
    db_path = db_url[len(SQLITE_FILE_URL_PREFIX):]
    if not db_path or db_path == SQLITE_IN_MEMORY_PATH:
        return None
    return db_path


def _ensure_sqlite_directory(db_url: str) -> None:
    """Create the directory for a file-based SQLite DB if it does not exist.

    `data/` is gitignored, so a freshly cloned copy has no such directory.
    SQLite does not create missing parents and fails with
    'unable to open database file' — the app would not start at all.
    """
    db_path = _sqlite_file(db_url)
    if db_path is None:
        return

    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def run_alembic_migrations(db_url: str) -> None:
    """Run all pending Alembic migrations up to head, backing the DB up first."""
    from pathlib import Path as _Path

    from alembic import command
    from alembic.config import Config

    # alembic/ lives at backend/src/backend/alembic/ — find it relative to this file.
    alembic_dir = _Path(__file__).parent.parent.parent / "alembic"
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    if _has_pending_migrations(cfg, db_url):
        from backend.infrastructure.persistence.database_backup import DatabaseBackup

        db_path = _sqlite_file(db_url)
        assert db_path is not None
        DatabaseBackup(_Path(db_path)).take()
    command.upgrade(cfg, "head")


def _has_pending_migrations(cfg: Config, db_url: str) -> bool:
    """An existing file DB, already migrated before, that is behind the newest migration."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    db_path = _sqlite_file(db_url)
    if db_path is None or not os.path.exists(db_path):
        return False
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            current = set(MigrationContext.configure(conn).get_current_heads())
    finally:
        engine.dispose()
    return bool(current) and current != set(ScriptDirectory.from_config(cfg).get_heads())


def _enable_sqlite_foreign_keys(
    dbapi_conn: sqlite3.Connection, _connection_record: object,
) -> None:
    """Enable FK enforcement for every SQLite connection.

    SQLite disables foreign keys by default. Without this, ondelete="CASCADE"
    on ForeignKey columns is silently ignored."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def _wait_for_locks(dbapi_conn: sqlite3.Connection, _connection_record: object) -> None:
    """A writer waits for another one to finish instead of failing at once."""
    cursor = dbapi_conn.cursor()
    cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    cursor.close()


def create_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""
    resolved_url = db_url or default_db_url()
    _ensure_sqlite_directory(resolved_url)
    engine = create_engine(resolved_url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    event.listen(engine, "connect", _wait_for_locks)
    return sessionmaker(bind=engine)


@cache
def app_session_factory() -> sessionmaker[Session]:
    """The process's one session factory, on the app's database: the API and the worker
    build all their sessions from it."""
    return create_session_factory()


def release_source_operations(session_factory: sessionmaker[Session]) -> None:
    """No long operation survives a restart: every source is free again."""
    from backend.infrastructure.persistence.sqla_source_operation_lock import (
        SqlaSourceOperationLock,
    )

    session = session_factory()
    try:
        SqlaSourceOperationLock(session).clear_all()
        session.commit()
    finally:
        session.close()


def cleanup_parse_cache(session_factory: sessionmaker[Session]) -> None:
    """Drop the cached parses of documents no source has any more."""
    from sqlalchemy import select

    from backend.infrastructure.adapters.caching_document_analyzer import document_hash
    from backend.infrastructure.persistence.document_json import load_document
    from backend.infrastructure.persistence.models import SourceDocumentModel
    from backend.infrastructure.persistence.sqla_parse_cache import SqlaParseCache

    with session_factory() as session:
        live = {
            document_hash(load_document(stored))
            for stored in session.scalars(select(SourceDocumentModel.document))
        }
    dropped = SqlaParseCache(session_factory).keep_only(live)
    if dropped:
        logger.info("Parse cache: dropped the parses of %d documents", dropped)


def reconcile_media_files(session_factory: sessionmaker[Session], media_root: str) -> None:
    """Remove orphan media files/directories without corresponding DB records.

    Two-phase scan on startup:
    Phase 1: for each source_id directory in media_root, verify source exists in DB.
             If not, remove the directory entirely.
    Phase 2: for each screenshot, clip or speech in a valid source directory —
             `p{phrase_id}_{kind}.{ext}` of a phrase, or `{candidate_id}_{kind}.{ext}` named
             before phrases — remove it
             only if no path column of the DB points at it and its phrase (or card) is gone.
             Files are never renamed: a word merged from several cards keeps the media of
             the others under their old ids, and the DB still points at them.
             A draft of a file being made is an orphan of a crash — no job runs at
             startup — and is removed.

    Orphan DB paths (file missing but DB still has path) are handled by the
    runtime lazy reconciler, not here.
    """
    import re
    import shutil

    from backend.application.utils.media_names import PHRASE_FILE_PREFIX
    from backend.infrastructure.adapters.local_media_files import DRAFT_PATTERN
    from backend.infrastructure.persistence.models import PhraseModel
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
        referenced = _referenced_media_paths(session)
        file_pattern = re.compile(r"^(p?)(\d+)_(screenshot|audio|tts)\.")

        def owner_exists(prefix: str, owner_id: int) -> bool:
            if prefix == PHRASE_FILE_PREFIX:
                return session.get(PhraseModel, owner_id) is not None
            return candidate_repo.get_by_id(owner_id) is not None

        def is_orphan(fname: str, fpath: str) -> bool:
            if DRAFT_PATTERN.match(fname):
                return True  # a draft left by a crash
            m = file_pattern.match(fname)
            if not m:
                return False  # unknown file, leave it
            return (
                os.path.realpath(fpath) not in referenced
                and not owner_exists(m.group(1), int(m.group(2)))
            )

        for entry in numeric_dirs:
            source_id = int(entry)
            source_dir = os.path.join(media_root, entry)

            if source_repo.get_by_id(source_id) is None:
                shutil.rmtree(source_dir, ignore_errors=True)
                logger.info("Reconcile: removed orphan media dir %s", source_dir)
                continue

            # Phase 2: check each file in the valid source directory
            for fname in os.listdir(source_dir):
                fpath = os.path.join(source_dir, fname)
                if not is_orphan(fname, fpath):
                    continue
                try:
                    os.remove(fpath)
                    logger.info("Reconcile: removed orphan media file %s", fpath)
                except OSError:
                    logger.warning(
                        "Reconcile: failed to remove orphan file %s", fpath, exc_info=True,
                    )
    finally:
        session.close()


def _referenced_media_paths(session: Session) -> set[str]:
    """Every file a path column of the DB points at: screenshots, clips, speech,
    pronunciations and pictures of words."""
    from sqlalchemy import select

    from backend.infrastructure.persistence.models import (
        CandidateMeaningImageModel,
        CandidateMediaModel,
        CandidatePronunciationModel,
        CandidateTTSModel,
    )

    columns = (
        CandidateMediaModel.screenshot_path,
        CandidateMediaModel.audio_path,
        CandidateTTSModel.audio_path,
        CandidatePronunciationModel.us_audio_path,
        CandidatePronunciationModel.uk_audio_path,
        CandidateMeaningImageModel.image_path,
    )
    paths: set[str] = set()
    for column in columns:
        paths.update(
            os.path.realpath(path)
            for path in session.scalars(select(column).where(column.is_not(None)))
            if path
        )
    return paths
