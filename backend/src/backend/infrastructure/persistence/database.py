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
    "You are a concise English dictionary assistant. "
    "Always return only the definition text — no labels, no commentary."
)

_DEFAULT_USER_TEMPLATE = (
    'Word: "{lemma}" (part of speech: {pos})\n'
    'Context: "{context}"\n\n'
    "Write a brief definition (1\u20132 sentences, max 30 words) for the specific meaning used in this context.\n"
    "Return only the definition text."
)


def upgrade_schema(session_factory: sessionmaker[Session]) -> None:
    """Apply incremental schema changes that create_all() cannot handle."""
    engine = session_factory.kw["bind"]
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN ai_meaning TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore

        # Seed default prompt — idempotent, runs on every startup
        conn.execute(
            text(
                "INSERT OR IGNORE INTO prompt_templates"
                " (function_key, name, description, system_prompt, user_template)"
                " VALUES (:fk, :name, :desc, :sys, :usr)"
            ),
            {
                "fk": "generate_meaning",
                "name": "Definition generation",
                "desc": "Generates a 1\u20132 sentence contextual definition (max 30 words)",
                "sys": _DEFAULT_SYSTEM_PROMPT,
                "usr": _DEFAULT_USER_TEMPLATE,
            },
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
            .values(status=SourceStatus.NEW.value)
        )
        session.commit()
    finally:
        session.close()
