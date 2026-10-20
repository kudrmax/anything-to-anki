"""`make fix-sections`: every phrase gets its section, the sources are rebuilt, nothing the
user decided or had generated changes, and a second run changes nothing."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.fix_sections import FixSectionsUseCase
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.database import create_session_factory
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from scripts.fix_sections import fix_sections
from tests.candidate_sorter_support import section_stamper
from tests.source_rebuild_support import SOURCE, Bench, at, word
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

TOPIC, SAVED = 10, 11


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def _fix(bench: Bench) -> FixSectionsUseCase:
    return FixSectionsUseCase(
        source_repo=bench.sources,
        occurrence_repo=bench.occurrences,
        stamper=section_stamper(SqlaSettingsRepository(bench.session)),
        rebuild_source=bench.rebuild(),
        unit_of_work=SqlaUnitOfWork(bench.session, bench.vocabulary.scope),
    )


def _unsectioned(bench: Bench) -> int:
    return int(bench.session.execute(
        text("SELECT count(*) FROM phrases WHERE earned_section IS NULL"),
    ).scalar_one())


def _processed_without_sections(bench: Bench) -> None:
    bench.processed(word("glare", at(0), at(1)), word("linger", at(3)))
    bench.decide_learn("linger", bench.phrase_on("linger", 3).id)
    bench.give_meaning(bench.phrase_on("glare", 0).id)
    bench.give_clip(bench.phrase_on("glare", 0).id, 0, 900)
    bench.session.execute(text("UPDATE phrases SET earned_section = NULL"))
    bench.session.commit()


def _results(bench: Bench) -> list[tuple[object, ...]]:
    bench.session.expire_all()
    return [tuple(row) for row in bench.session.execute(text(
        "SELECT p.id, p.choice, p.source_phrase, p.polished_phrase, p.polish_reverted,"
        " p.shown_by, p.edited_by_user, m.meaning, d.audio_path, d.start_ms, d.end_ms,"
        " t.audio_path, z.phrase_id"
        " FROM phrases p"
        " LEFT JOIN candidate_meanings m ON m.phrase_id = p.id"
        " LEFT JOIN candidate_media d ON d.phrase_id = p.id"
        " LEFT JOIN candidate_tts t ON t.phrase_id = p.id"
        " LEFT JOIN candidate_clozes z ON z.phrase_id = p.id"
        " ORDER BY p.id"
    ))]


def test_every_phrase_gets_a_section(bench: Bench) -> None:
    _processed_without_sections(bench)
    assert _unsectioned(bench) > 0

    report = _fix(bench).execute()

    assert _unsectioned(bench) == 0
    assert report.phrases_stamped > 0
    assert report.sources_rebuilt == 1
    assert report.failed == []


def test_decisions_and_generation_are_unchanged(bench: Bench) -> None:
    _processed_without_sections(bench)
    before = _results(bench)
    assert any(row[7] is not None for row in before)
    assert any(row[1] == "learn" for row in before)

    _fix(bench).execute()

    assert _results(bench) == before


def test_a_second_run_changes_nothing(bench: Bench) -> None:
    _processed_without_sections(bench)
    _fix(bench).execute()
    sections = bench.session.execute(
        text("SELECT id, earned_section FROM phrases ORDER BY id"),
    ).all()

    second = _fix(bench).execute()

    assert second.phrases_stamped == 0
    assert bench.rebuild().preview(SOURCE).without_open.nothing_to_update
    bench.session.expire_all()
    assert bench.session.execute(
        text("SELECT id, earned_section FROM phrases ORDER BY id"),
    ).all() == sections


def test_a_source_that_fails_is_reported_and_the_others_still_go(bench: Bench) -> None:
    _processed_without_sections(bench)
    assert bench.lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    bench.session.commit()

    report = _fix(bench).execute()

    assert report.failed == [SOURCE]
    assert report.sources_rebuilt == 0
    assert _unsectioned(bench) == 0


def _file_database(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'app.db'}"


def _seed_sources_without_text(db_url: str) -> None:
    """A topic and saved phrases, each with a phrase without a section; both are busy, as
    a crash leaves them."""
    from backend.infrastructure.persistence.database import run_alembic_migrations

    run_alembic_migrations(db_url)
    factory = create_session_factory(db_url)
    with factory() as session:
        for source_id, role, word_id in ((TOPIC, "topic", 1), (SAVED, "saved_phrases", 2)):
            session.execute(
                text(
                    "INSERT INTO sources (id, title, status, role, created_at)"
                    " VALUES (:id, 'title', 'done', :role, '2026-01-01 00:00:00')"
                ),
                {"id": source_id, "role": role},
            )
            insert_word(session, word_id, source_id=source_id, lemma=f"lemma{word_id}")
            SqlaSourceOperationLock(session).acquire(source_id, SourceOperationKind.REBUILD)
        session.execute(text("UPDATE phrases SET earned_section = NULL"))
        session.commit()


def test_a_leftover_operation_lock_does_not_block_the_script(tmp_path: Path) -> None:
    db_url = _file_database(tmp_path)
    _seed_sources_without_text(db_url)

    report = fix_sections(db_url)

    with create_session_factory(db_url)() as session:
        sources = session.execute(text("SELECT count(*) FROM sources")).scalar_one()
        held = session.execute(text("SELECT count(*) FROM source_operations")).scalar_one()
    assert report.failed == []
    assert report.sources_rebuilt == sources
    assert report.phrases_stamped == 2
    assert held == 0


def test_topics_and_saved_phrases_are_rebuilt_sections_only(tmp_path: Path) -> None:
    db_url = _file_database(tmp_path)
    _seed_sources_without_text(db_url)
    factory = create_session_factory(db_url)
    with factory() as session:
        before = session.execute(text(
            "SELECT id, source_phrase, polished_phrase, shown_by, choice, origin"
            " FROM phrases ORDER BY id"
        )).all()

    fix_sections(db_url)

    with factory() as session:
        after = session.execute(text(
            "SELECT id, source_phrase, polished_phrase, shown_by, choice, origin"
            " FROM phrases ORDER BY id"
        )).all()
        unsectioned = session.execute(
            text("SELECT count(*) FROM phrases WHERE earned_section IS NULL"),
        ).scalar_one()
    assert after == before
    assert [row[0] for row in after] == [phrase_id_of(1), phrase_id_of(2)]
    assert unsectioned == 0
