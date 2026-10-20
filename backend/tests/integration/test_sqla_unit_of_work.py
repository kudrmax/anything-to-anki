from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from backend.domain.exceptions import NestedWriteError
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

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
    unit_of_work._session.execute(
        text(
            "INSERT INTO sources (id, title, status, created_at)"
            " VALUES (:id, 'title', 'done', '2026-01-01 00:00:00')"
        ),
        {"id": SOURCE_ID},
    )


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
        assert _source_count_without_lock(unit_of_work) == 1
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


def _source_count_without_lock(unit_of_work: SqlaUnitOfWork) -> int:
    return unit_of_work._session.execute(text("SELECT COUNT(*) FROM sources")).scalar_one()
