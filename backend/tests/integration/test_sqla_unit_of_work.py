from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import backend.infrastructure.persistence.models  # noqa: F401  registers every table on Base
import pytest
from backend.domain.exceptions import NestedWriteError, UncommittedWorkError
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.models import SourceModel
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import Engine, create_engine, event, insert, select, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source

SOURCE_ID = 1


@pytest.fixture()
def engine(tmp_path: Path) -> Iterator[Engine]:
    """A file database: a second session sees only what the first one committed."""
    file_engine = create_engine(f"sqlite:///{tmp_path / 'uow.db'}")
    event.listen(file_engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(file_engine)
    yield file_engine
    file_engine.dispose()


@pytest.fixture()
def unit_of_work(engine: Engine) -> Iterator[SqlaUnitOfWork]:
    session = sessionmaker(bind=engine)()
    yield SqlaUnitOfWork(session, MagicMock())
    session.close()


def _add_source(unit_of_work: SqlaUnitOfWork) -> None:
    insert_source(unit_of_work._session, SOURCE_ID)


def _count_in_open_transaction(unit_of_work: SqlaUnitOfWork) -> int:
    return unit_of_work._session.execute(text("SELECT COUNT(*) FROM sources")).scalar_one()


def _source_count(engine: Engine) -> int:
    with Session(engine) as other_session:
        return other_session.execute(text("SELECT COUNT(*) FROM sources")).scalar_one()


def test_write_commits_on_exit(unit_of_work: SqlaUnitOfWork, engine: Engine) -> None:
    with unit_of_work.write():
        _add_source(unit_of_work)

    assert _source_count(engine) == 1


def test_write_rolls_back_on_error(unit_of_work: SqlaUnitOfWork, engine: Engine) -> None:
    with pytest.raises(RuntimeError), unit_of_work.write():
        _add_source(unit_of_work)
        raise RuntimeError

    assert _source_count(engine) == 0


def test_nested_write_raises(unit_of_work: SqlaUnitOfWork) -> None:
    with pytest.raises(NestedWriteError), unit_of_work.write(), unit_of_work.write():
        pass


def test_nested_write_does_not_commit_the_outer_work(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    with pytest.raises(RuntimeError), unit_of_work.write():
        _add_source(unit_of_work)
        with pytest.raises(NestedWriteError), unit_of_work.write():
            pass
        assert _count_in_open_transaction(unit_of_work) == 1
        raise RuntimeError

    assert _source_count(engine) == 0


def test_nested_write_does_not_roll_back_the_outer_work(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    with unit_of_work.write():
        _add_source(unit_of_work)
        with pytest.raises(NestedWriteError), unit_of_work.write():
            pass

    assert _source_count(engine) == 1


def test_write_after_nested_error_still_works(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    with pytest.raises(NestedWriteError), unit_of_work.write(), unit_of_work.write():
        pass

    with unit_of_work.write():
        _add_source(unit_of_work)

    assert _source_count(engine) == 1


def test_nested_write_through_another_unit_of_work_on_the_session_raises(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    other = SqlaUnitOfWork(unit_of_work._session, MagicMock())
    with pytest.raises(RuntimeError), unit_of_work.write():
        _add_source(unit_of_work)
        with pytest.raises(NestedWriteError), other.write():
            pass
        assert _count_in_open_transaction(unit_of_work) == 1
        assert _source_count(engine) == 0
        raise RuntimeError

    assert _source_count(engine) == 0


def test_another_unit_of_work_writes_after_the_first_closes(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    other = SqlaUnitOfWork(unit_of_work._session, MagicMock())
    with unit_of_work.write():
        pass
    with other.write():
        _add_source(other)

    assert _source_count(engine) == 1


def test_pending_object_on_entry_raises_and_writes_nothing(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    unit_of_work._session.add(SourceModel(id=SOURCE_ID, title="title", status="done"))

    with pytest.raises(UncommittedWorkError), unit_of_work.write():
        pass

    assert _source_count(engine) == 0


def test_flushed_object_on_entry_raises_and_writes_nothing(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    session = unit_of_work._session
    session.add(SourceModel(id=SOURCE_ID, title="title", status="done"))
    session.execute(select(SourceModel)).all()

    with pytest.raises(UncommittedWorkError), unit_of_work.write():
        pass

    session.rollback()
    assert _source_count(engine) == 0


def test_core_write_on_entry_raises_and_writes_nothing(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    session = unit_of_work._session
    session.execute(insert(SourceModel).values(id=SOURCE_ID, title="title", status="done"))

    with pytest.raises(UncommittedWorkError), unit_of_work.write():
        pass

    session.rollback()
    assert _source_count(engine) == 0


def test_session_that_only_read_enters_a_write(
    unit_of_work: SqlaUnitOfWork, engine: Engine
) -> None:
    session = unit_of_work._session
    assert _count_in_open_transaction(unit_of_work) == 0
    session.execute(select(SourceModel)).all()
    session.execute(text("SELECT 1")).all()

    with unit_of_work.write():
        _add_source(unit_of_work)

    assert _source_count(engine) == 1
