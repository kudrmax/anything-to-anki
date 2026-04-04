import pytest
from backend.infrastructure.persistence.database import Base
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def db_session() -> Session:
    """Create an in-memory SQLite session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()
