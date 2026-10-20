from __future__ import annotations

from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime

import pytest
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_eviction import SourceEviction
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_collection_repository import SqlaCollectionRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


@pytest.mark.integration
class TestSqlaCollectionRepository:
    def test_round_trip_and_save(self, session: Session) -> None:
        repo = SqlaCollectionRepository(session)
        top = repo.create(Collection(name="Friends", position=0))
        assert top.id is not None
        sub = repo.create(Collection(name="Season 1", parent_id=top.id, position=0))
        assert sub.id is not None
        deleted_at = datetime(2026, 10, 14, tzinfo=UTC)
        repo.save(
            [Collection(id=sub.id, name="S1", parent_id=None, position=3, deleted_at=deleted_at)],
        )
        stored = repo.get_by_id(sub.id)
        assert stored is not None
        assert (stored.name, stored.parent_id, stored.position, stored.deleted_at) == (
            "S1", None, 3, deleted_at,
        )
        assert [c.name for c in repo.list_all()] == ["Friends"]
        assert {c.name for c in repo.list_all(include_deleted=True)} == {"Friends", "S1"}

    def test_same_name_allowed_under_different_parents(self, session: Session) -> None:
        repo = SqlaCollectionRepository(session)
        a = repo.create(Collection(name="Friends"))
        b = repo.create(Collection(name="Lost", position=1))
        repo.create(Collection(name="Season 1", parent_id=a.id))
        repo.create(Collection(name="Season 1", parent_id=b.id))

    def test_live_siblings_names_are_unique_in_db(self, session: Session) -> None:
        repo = SqlaCollectionRepository(session)
        repo.create(Collection(name="Worm"))
        with pytest.raises(IntegrityError):
            repo.create(Collection(name="Worm", position=1))

    def test_evictions_are_taken_once(self, session: Session) -> None:
        repo = SqlaCollectionRepository(session)
        sources = SqlaSourceRepository(session, SessionChangeRecorder(session))
        top = repo.create(Collection(name="Friends"))
        assert top.id is not None
        source = sources.create(
            Source(status=SourceStatus.NEW, title="Pilot", collection_id=top.id),
        )
        assert source.id is not None
        eviction = SourceEviction(source.id, top.id, None)
        repo.record_evictions(top.id, [eviction])
        assert repo.take_evictions(top.id) == [eviction]
        assert repo.take_evictions(top.id) == []


@pytest.mark.integration
def test_set_collections(session: Session) -> None:
    collections = SqlaCollectionRepository(session)
    sources = SqlaSourceRepository(session, SessionChangeRecorder(session))
    top = collections.create(Collection(name="IELTS"))
    a = sources.create(Source(status=SourceStatus.NEW, title="a"))
    b = sources.create(Source(status=SourceStatus.NEW, title="b", collection_id=top.id))
    assert a.id is not None and b.id is not None
    sources.set_collections({a.id: top.id, b.id: None})
    assert sources.get_by_id(a.id).collection_id == top.id  # type: ignore[union-attr]
    assert sources.get_by_id(b.id).collection_id is None  # type: ignore[union-attr]
