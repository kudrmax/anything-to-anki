from __future__ import annotations

from sqlalchemy import create_engine, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.domain.value_objects.source_status import SourceStatus


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def create_session_factory(db_url: str = "sqlite:///vocabminer.db") -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
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
            .values(status=SourceStatus.NEW.value)
        )
        session.commit()
    finally:
        session.close()
