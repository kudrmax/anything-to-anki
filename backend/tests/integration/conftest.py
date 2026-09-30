import pytest
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def db_session() -> Session:
    """Create an in-memory SQLite session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def insert_source(session: Session, source_id: int) -> None:
    """Insert a minimal source row: candidates reference sources by FK."""
    session.execute(
        text(
            "INSERT INTO sources (id, raw_text, title, status, input_method,"
            " content_type, created_at)"
            " VALUES (:id, 'text', 'title', 'done', 'text_pasted', 'text',"
            " '2026-01-01 00:00:00')"
        ),
        {"id": source_id},
    )


@pytest.fixture()
def source_id(db_session: Session) -> int:
    """A persisted source that candidates in the test can belong to."""
    default_source_id = 1
    insert_source(db_session, default_source_id)
    return default_source_id
