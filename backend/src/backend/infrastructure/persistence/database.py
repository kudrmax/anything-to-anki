from __future__ import annotations

import os

from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.domain.value_objects.source_status import SourceStatus


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def _default_db_url() -> str:
    data_dir = os.getenv("DATA_DIR", ".")
    db_file = "vocabminer.db" if os.getenv("APP_ENV") == "production" else "vocabminer_dev.db"
    return f"sqlite:///{data_dir}/{db_file}"


def create_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""
    engine = create_engine(db_url or _default_db_url(), connect_args={"check_same_thread": False})
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
            conn.execute(text("ALTER TABLE sources ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'text'"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN is_phrasal_verb BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN definition TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN ipa VARCHAR(100)"))
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

        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN meaning TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("UPDATE candidates SET meaning = COALESCE(ai_meaning, definition) WHERE meaning IS NULL"))
            conn.commit()
        except Exception:
            pass

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
            conn.execute(text("ALTER TABLE generation_jobs ADD COLUMN candidate_ids_json TEXT NOT NULL DEFAULT '[]'"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        try:
            conn.execute(text("ALTER TABLE generation_jobs ADD COLUMN skipped_candidates INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

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


def resume_generation_jobs(session_factory: sessionmaker[Session]) -> None:
    """Mark RUNNING/PENDING generation jobs as FAILED on startup (crash recovery).

    Jobs left in RUNNING or PENDING state after a crash are stale — the worker
    is no longer running. Mark them FAILED so the user can start a fresh job.
    """
    from backend.infrastructure.persistence.models import GenerationJobModel

    session = session_factory()
    try:
        session.execute(
            update(GenerationJobModel)
            .where(GenerationJobModel.status.in_(["running", "pending"]))
            .values(status="failed")
        )
        session.commit()
    finally:
        session.close()
