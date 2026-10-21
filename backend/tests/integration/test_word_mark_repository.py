"""A lemma carries one mark, Known (in some parts of speech) or Unknown, and every change of
a mark is recorded."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.card_change import MarkChanged
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_word_mark_repository import SqlaWordMarkRepository
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.word_marks_support import insert_known, known_rows, unknown_lemmas

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class Marks:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.recorder = SessionChangeRecorder(session)
        self.repo = SqlaWordMarkRepository(session, self.recorder)

    def recorded(self) -> set[MarkChanged]:
        return {change for change in self.recorder.drain() if isinstance(change, MarkChanged)}


@pytest.fixture
def marks(db_session: Session) -> Marks:
    return Marks(db_session)


def test_mark_known_stores_the_lemma_lower_case_with_its_pos(marks: Marks) -> None:
    entry = marks.repo.mark_known("Glare", "VERB")

    assert (entry.lemma, entry.pos) == ("glare", "VERB")
    assert entry.id is not None
    assert known_rows(marks.session) == {("glare", "VERB")}
    assert marks.recorded() == {MarkChanged("glare")}


def test_mark_known_again_changes_and_records_nothing(marks: Marks) -> None:
    first = marks.repo.mark_known("glare", "VERB")
    marks.recorder.drain()

    again = marks.repo.mark_known("Glare", "VERB")

    assert again == first
    assert marks.recorded() == set()


def test_a_second_pos_adds_an_entry(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.recorder.drain()

    marks.repo.mark_known("glare", "NOUN")

    assert known_rows(marks.session) == {("glare", "VERB"), ("glare", "NOUN")}
    assert marks.recorded() == {MarkChanged("glare")}


def test_any_pos_absorbs_the_others(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.repo.mark_known("glare", "NOUN")

    entry = marks.repo.mark_known("glare", None)

    assert entry.pos is None
    assert known_rows(marks.session) == {("glare", None)}


def test_a_pos_under_any_pos_is_already_covered(marks: Marks) -> None:
    marks.repo.mark_known("glare", None)
    marks.recorder.drain()

    entry = marks.repo.mark_known("glare", "VERB")

    assert entry.pos is None
    assert known_rows(marks.session) == {("glare", None)}
    assert marks.recorded() == set()


def test_known_replaces_unknown(marks: Marks) -> None:
    marks.repo.mark_unknown("glare")
    marks.recorder.drain()

    marks.repo.mark_known("glare", "VERB")

    assert unknown_lemmas(marks.session) == set()
    assert known_rows(marks.session) == {("glare", "VERB")}
    assert marks.recorded() == {MarkChanged("glare")}


def test_unknown_replaces_known_with_every_pos(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.repo.mark_known("glare", "NOUN")
    marks.recorder.drain()

    entry = marks.repo.mark_unknown("Glare")

    assert entry.lemma == "glare"
    assert entry.id is not None
    assert known_rows(marks.session) == set()
    assert unknown_lemmas(marks.session) == {"glare"}
    assert marks.recorded() == {MarkChanged("glare")}


def test_mark_unknown_again_records_nothing(marks: Marks) -> None:
    first = marks.repo.mark_unknown("glare")
    marks.recorder.drain()

    assert marks.repo.mark_unknown("GLARE") == first
    assert marks.recorded() == set()


def test_removing_one_entry_keeps_the_others(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.repo.mark_known("glare", "NOUN")
    marks.recorder.drain()

    marks.repo.remove_known_entry("Glare", "VERB")

    assert known_rows(marks.session) == {("glare", "NOUN")}
    assert marks.repo.known_lemmas() == {"glare"}
    assert marks.recorded() == {MarkChanged("glare")}


def test_removing_the_last_entry_removes_the_mark(marks: Marks) -> None:
    marks.repo.mark_known("glare", None)

    marks.repo.remove_known_entry("glare", None)

    assert marks.repo.known_lemmas() == set()
    assert marks.session.execute(text("SELECT count(*) FROM word_marks")).scalar_one() == 0


def test_a_removed_entry_can_be_marked_again(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.repo.remove_known_entry("glare", "VERB")

    marks.repo.mark_known("glare", "VERB")

    assert known_rows(marks.session) == {("glare", "VERB")}


def test_remove_known_takes_every_pos(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.repo.mark_known("glare", "NOUN")
    marks.recorder.drain()

    marks.repo.remove_known("GLARE")

    assert known_rows(marks.session) == set()
    assert marks.recorded() == {MarkChanged("glare")}


def test_remove_known_leaves_an_unknown_mark(marks: Marks) -> None:
    marks.repo.mark_unknown("glare")
    marks.recorder.drain()

    marks.repo.remove_known("glare")
    marks.repo.remove_known_entry("glare", None)

    assert unknown_lemmas(marks.session) == {"glare"}
    assert marks.recorded() == set()


def test_remove_unknown_leaves_a_known_mark(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")
    marks.recorder.drain()

    marks.repo.remove_unknown("glare")

    assert known_rows(marks.session) == {("glare", "VERB")}
    assert marks.recorded() == set()


def test_remove_unknown(marks: Marks) -> None:
    marks.repo.mark_unknown("glare")
    marks.recorder.drain()

    marks.repo.remove_unknown("Glare")

    assert unknown_lemmas(marks.session) == set()
    assert marks.recorded() == {MarkChanged("glare")}


def test_entries_list_newest_mark_first(marks: Marks) -> None:
    insert_known(marks.session, "abide", "VERB", created_at="2026-01-01 00:00:00")
    insert_known(marks.session, "bask", "VERB", "NOUN", created_at="2026-02-01 00:00:00")
    marks.repo.mark_unknown("cower")

    known = [(e.lemma, e.pos) for e in marks.repo.known_entries()]
    unknown = [e.lemma for e in marks.repo.unknown_entries()]

    assert known == [("bask", "NOUN"), ("bask", "VERB"), ("abide", "VERB")]
    assert unknown == ["cower"]
    assert len({e.id for e in marks.repo.known_entries()}) == len(known)


def test_lemmas_and_counts_per_mark(marks: Marks) -> None:
    marks.repo.mark_known("abide", "VERB")
    marks.repo.mark_known("abide", "NOUN")
    marks.repo.mark_known("bask", None)
    marks.repo.mark_unknown("cower")

    assert marks.repo.known_lemmas() == {"abide", "bask"}
    assert marks.repo.unknown_lemmas() == {"cower"}
    assert (marks.repo.known_count(), marks.repo.unknown_count()) == (2, 1)


def test_the_schema_holds_one_mark_per_lemma(marks: Marks) -> None:
    marks.repo.mark_known("glare", "VERB")

    with pytest.raises(IntegrityError):
        marks.session.execute(text(
            "INSERT INTO word_marks (lemma, mark, created_at)"
            " VALUES ('glare', 'unknown', '2026-01-01')"
        ))


def test_the_schema_holds_one_any_pos_row_per_lemma(marks: Marks) -> None:
    marks.repo.mark_known("glare", None)

    with pytest.raises(IntegrityError):
        marks.session.execute(
            text("INSERT INTO known_pos (lemma, pos) VALUES ('glare', NULL)"),
        )


def test_the_schema_takes_only_known_or_unknown(marks: Marks) -> None:
    with pytest.raises(IntegrityError):
        marks.session.execute(text(
            "INSERT INTO word_marks (lemma, mark, created_at)"
            " VALUES ('glare', 'maybe', '2026-01-01')"
        ))


def test_entry_ids_survive_a_vacuum(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'marks.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        marks = Marks(session)
        for lemma in ("abide", "bask", "cower", "dwell"):
            marks.repo.mark_known(lemma, "VERB")
            marks.repo.mark_known(lemma, "NOUN")
        marks.repo.mark_unknown("evade")
        marks.repo.mark_unknown("fret")
        marks.repo.remove_known("abide")
        marks.repo.remove_known_entry("bask", "VERB")
        marks.repo.remove_unknown("evade")
        session.commit()
        before = _ids(marks.repo)
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT").exec_driver_sql("VACUUM")
    with Session(engine) as session:
        assert _ids(SqlaWordMarkRepository(session, SessionChangeRecorder(session))) == before
    engine.dispose()


def _ids(repo: SqlaWordMarkRepository) -> set[tuple[int | None, str, str | None]]:
    return {(e.id, e.lemma, e.pos) for e in repo.known_entries()} | {
        (e.id, e.lemma, "unknown") for e in repo.unknown_entries()
    }
