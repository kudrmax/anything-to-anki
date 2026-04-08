from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.domain.value_objects.source_status import SourceStatus

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def default_db_url() -> str:
    data_dir = os.getenv("DATA_DIR", ".")
    db_file = "vocabminer.db" if os.getenv("APP_ENV") == "production" else "vocabminer_dev.db"
    return f"sqlite:///{data_dir}/{db_file}"


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


_DEFAULT_SYSTEM_PROMPT = (
    "You are a vocabulary assistant for a B1-B2 English learner. "
    "Your task is to explain English words clearly and simply, "
    "using only common everyday English in your explanations.\n\n"
    "For the 'meaning' field, provide:\n"
    "- LINE 1: Definition using the word in a natural sentence pattern "
    "that shows how it works in speech. "
    'NOT "X means Y". Instead, a real phrase: '
    '"When you **elaborate** on something, you give more details about it", '
    '"If you are **reluctant** to do something, you don\'t really want to do it". '
    "Bold the target word using **bold**. "
    "Must match the SPECIFIC meaning used in the given context.\n"
    "- LINE 2: Context explanation \u2014 explain what is happening in the given context "
    "in simple words. Rephrase the situation. "
    'NEVER evaluate how well the word fits. No "this word fits perfectly".\n'
    "- LINE 3: \U0001f1f7\U0001f1fa <short Russian translation, 1-3 words>\n"
    "- LINE 4: \U0001f4cb <2-3 English synonyms or short phrases> "
    "(only for the specific meaning used in context)\n\n"
    "For the 'ipa' field, provide the IPA transcription of the word "
    "(e.g., /\u026a\u02c8l\u00e6b.\u0259.re\u026at/ for 'elaborate')."
)

_DEFAULT_USER_TEMPLATE = 'Word: "{lemma}" ({pos})\nContext: "{context}"'


def upgrade_schema(session_factory: sessionmaker[Session]) -> None:
    """Apply incremental schema changes that create_all() cannot handle."""
    engine = session_factory.kw["bind"]
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN ai_meaning TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text(
                "ALTER TABLE sources ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'text'"
            ))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text(
                "ALTER TABLE candidates ADD COLUMN is_phrasal_verb BOOLEAN NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN definition TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE sources ADD COLUMN processing_stage VARCHAR(30)"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE sources ADD COLUMN title VARCHAR(200)"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS generation_jobs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "source_id INTEGER, "
            "status VARCHAR(20) NOT NULL DEFAULT 'pending', "
            "total_candidates INTEGER NOT NULL, "
            "processed_candidates INTEGER NOT NULL DEFAULT 0, "
            "failed_candidates INTEGER NOT NULL DEFAULT 0, "
            "skipped_candidates INTEGER NOT NULL DEFAULT 0, "
            "candidate_ids_json TEXT NOT NULL DEFAULT '[]', "
            "created_at DATETIME NOT NULL DEFAULT (datetime('now'))"
            ")"
        ))
        conn.commit()

        try:
            conn.execute(text(
                "ALTER TABLE generation_jobs"
                " ADD COLUMN candidate_ids_json TEXT NOT NULL DEFAULT '[]'"
            ))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text(
                "ALTER TABLE generation_jobs"
                " ADD COLUMN skipped_candidates INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        # --- Video media attachments ---
        try:
            conn.execute(text("ALTER TABLE sources ADD COLUMN video_path TEXT"))
            conn.commit()
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE sources ADD COLUMN audio_track_index INTEGER"))
            conn.commit()
        except Exception:
            pass

        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS media_extraction_jobs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "source_id INTEGER, "
            "status VARCHAR(20) NOT NULL DEFAULT 'pending', "
            "total_candidates INTEGER NOT NULL, "
            "processed_candidates INTEGER NOT NULL DEFAULT 0, "
            "failed_candidates INTEGER NOT NULL DEFAULT 0, "
            "skipped_candidates INTEGER NOT NULL DEFAULT 0, "
            "candidate_ids_json TEXT NOT NULL DEFAULT '[]', "
            "created_at DATETIME NOT NULL DEFAULT (datetime('now'))"
            ")"
        ))
        conn.commit()

        # Rename settings key: anki_field_screenshot → anki_field_image
        try:
            conn.execute(text(
                "UPDATE settings SET key = 'anki_field_image' "
                "WHERE key = 'anki_field_screenshot' "
                "AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'anki_field_image')"
            ))
            conn.execute(text(
                "DELETE FROM settings WHERE key = 'anki_field_screenshot'"
            ))
            conn.commit()
        except Exception:
            pass

        # Seed default prompt — idempotent, runs on every startup
        conn.execute(
            text(
                "INSERT OR IGNORE INTO prompt_templates"
                " (function_key, system_prompt, user_template)"
                " VALUES (:fk, :sys, :usr)"
            ),
            {
                "fk": "generate_meaning",
                "sys": _DEFAULT_SYSTEM_PROMPT,
                "usr": _DEFAULT_USER_TEMPLATE,
            },
        )
        # Force-update prompt to current version (adds IPA support)
        conn.execute(
            text(
                "UPDATE prompt_templates SET system_prompt = :sys"
                " WHERE function_key = :fk AND system_prompt NOT LIKE '%ipa%'"
            ),
            {"fk": "generate_meaning", "sys": _DEFAULT_SYSTEM_PROMPT},
        )
        conn.commit()


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


def _count_sources(session: Session) -> int:
    """Count rows in `sources` table. Extracted as a helper so tests can patch it."""
    from sqlalchemy import func, select

    from backend.infrastructure.persistence.models import SourceModel

    result = session.execute(select(func.count()).select_from(SourceModel)).scalar()
    return int(result or 0)


def reconcile_media_files(session_factory: sessionmaker[Session], media_root: str) -> None:
    """Remove orphan media files/directories without corresponding DB records.

    Two-phase scan on startup:
    Phase 1: for each source_id directory in media_root, verify source exists in DB.
             If not, remove the directory entirely.
    Phase 2: for each `{candidate_id}_{kind}.{ext}` file in a valid source directory,
             verify the candidate exists in DB. If not, remove the file.

    SAFETY GUARD: aborts the entire reconcile if the DB has fewer sources than
    the on-disk media root has source directories. This catches the case where
    the wrong DB was loaded (e.g. APP_ENV misconfigured at startup) — in that
    scenario the dev DB might be empty but the prod media root would have many
    source dirs, and the old behaviour would `rmtree` all of them.

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
        # Defensive guard: refuse to run if DB has fewer sources than disk dirs.
        # In a healthy state the DB always has at least as many sources as on-disk
        # media dirs (a source can have no media yet, but media never exists for a
        # source that doesn't have a DB row — DeleteSourceUseCase cascades).
        # If we see the opposite, the wrong DB was almost certainly loaded.
        db_source_count = _count_sources(session)
        if db_source_count < len(numeric_dirs):
            logger.error(
                "Reconcile ABORTED: DB has %d sources but media_root has %d source "
                "dirs (%s). This almost certainly means the wrong DB was loaded — "
                "check APP_ENV. Skipping cleanup to avoid data loss.",
                db_source_count, len(numeric_dirs), sorted(numeric_dirs),
            )
            return

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
