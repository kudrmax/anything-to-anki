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
    "Output has 4 lines. Follow the format exactly, no extra lines or labels.\n\n"
    "LINE 1 — Definition:\n"
    "Use the word itself inside a natural sentence pattern that shows how it works in speech.\n"
    'NOT "X means Y". Instead, a real phrase: '
    '"When you **elaborate** on something, you give more details about it", '
    '"If you are **reluctant** to do something, you don\'t really want to do it".\n'
    "This shows the learner the part of speech, grammar, and how the word fits in real sentences.\n"
    "Bold the target word using **bold**.\n"
    "Must match the SPECIFIC meaning used in the given context, not a general one.\n\n"
    "LINE 2 — Context explanation:\n"
    "Explain what is happening in the given context in simple words.\n"
    "Rephrase the situation: what is happening, why, what it feels like.\n"
    "Imagine explaining the sentence to a friend who doesn't know this word.\n"
    'NEVER evaluate how well the word fits. No "this word fits perfectly", '
    '"this perfectly captures", "this is a great example of".\n\n'
    "LINE 3 — \U0001f1f7\U0001f1fa <short Russian translation, 1-3 words>\n"
    "Short, natural — not a dictionary entry.\n\n"
    "LINE 4 — \U0001f4cb <2-3 English synonyms or short phrases>\n"
    "Only for the specific meaning used in context."
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
