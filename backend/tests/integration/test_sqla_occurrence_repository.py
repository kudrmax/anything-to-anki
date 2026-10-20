"""The phrases of words: storing, rewriting their text and words, marks and results."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice, NoteKind
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_generation import PhraseGeneration
from backend.domain.value_objects.phrase_origin_kind import ShownBy
from backend.infrastructure.persistence.models import (
    JobModel,
)
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select, text, update

from tests.integration.conftest import insert_source
from tests.phrase_support import make_occurrence, phrase, shown_lemmas
from tests.word_support import CREATED_AT, bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE = 1
OTHER_SOURCE = 2
WORD = 10
WORD_PHRASE = phrase_id_of(WORD)
OTHER_WORD = 20
NOTE = 555
POSITION = DocumentPosition(block=1, start_line=0, start_char=0, end_line=0, end_char=16)


@pytest.fixture
def repo(db_session: Session) -> SqlaOccurrenceRepository:
    insert_source(db_session, SOURCE)
    insert_source(db_session, OTHER_SOURCE)
    insert_word(db_session, WORD, source_id=SOURCE, lemma="glare")
    insert_word(db_session, OTHER_WORD, source_id=OTHER_SOURCE, lemma="linger")
    db_session.flush()
    return SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session))


def _words(session: Session, phrase_id: int) -> set[str]:
    return shown_lemmas(session, phrase_id)


def _added(repo: SqlaOccurrenceRepository, text: str = "He glared at me.") -> int:
    added = repo.add(replace(
        make_occurrence(text, candidate_id=WORD),
        key=OccurrenceKey(block=1, line=0, char=3), phrase_position=POSITION,
    ))
    assert added.id is not None
    return added.id


def test_add_stores_the_phrase_and_its_words(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.key == OccurrenceKey(block=1, line=0, char=3)
    assert stored.phrase_position == POSITION
    assert stored.source_phrase.text == "He glared at me."
    assert _words(db_session, phrase_id) == {"he", "glared", "at", "me"}


def test_write_text_rewrites_words_from_the_polished_text(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)

    repo.write_text(
        phrase_id, phrase("He glared at me."), POSITION, polished=phrase("He stared at us"),
        earned_section=CandidateSection.READY,
    )

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.phrase.text == "He stared at us"
    assert _words(db_session, phrase_id) == {"he", "stared", "at", "us"}


def test_write_text_with_a_reverted_polish_keeps_the_words_of_the_source(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)

    repo.write_text(
        phrase_id, phrase("He glared at me."), POSITION,
        earned_section=CandidateSection.READY,
        polished=phrase("He stared at us"), polish_reverted=True,
    )

    assert _words(db_session, phrase_id) == {"he", "glared", "at", "me"}


def test_a_write_that_changes_the_shown_text_bumps_the_revision(
    repo: SqlaOccurrenceRepository,
) -> None:
    phrase_id = _added(repo)

    repo.write_text(
        phrase_id, phrase("He glared again."), POSITION, earned_section=CandidateSection.READY,
    )

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.revision == 1
    assert stored.source_phrase.text == "He glared again."


def test_a_write_that_keeps_the_shown_text_does_not_bump(
    repo: SqlaOccurrenceRepository,
) -> None:
    phrase_id = _added(repo)
    same = phrase("He glared at me.")

    repo.write_text(
        phrase_id, same, POSITION, earned_section=CandidateSection.READY, polished=same,
    )
    repo.write_text(
        phrase_id, same, POSITION, earned_section=CandidateSection.READY,
        polished=phrase("He stared."), polish_reverted=True,
    )

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.revision == 0


def _job(session: Session, phrase_id: int, job_type: JobType, status: JobStatus) -> None:
    SqlaJobRepository(session).enqueue([Job.queued(
        job_type, SOURCE, WORD, phrase_id=phrase_id, phrase_revision=0,
    )])
    session.execute(
        update(JobModel)
        .where(JobModel.phrase_id == phrase_id, JobModel.job_type == job_type.value)
        .values(status=status.value)
    )


def _jobs(session: Session, phrase_id: int) -> dict[str, tuple[str, int | None]]:
    return {
        job.job_type: (job.status, job.phrase_revision)
        for job in session.scalars(select(JobModel).where(JobModel.phrase_id == phrase_id))
    }


def test_queued_jobs_of_a_phrase_follow_its_new_text_running_ones_do_not(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    _job(db_session, phrase_id, JobType.MEANING, JobStatus.QUEUED)
    _job(db_session, phrase_id, JobType.MEDIA, JobStatus.QUEUED)
    _job(db_session, phrase_id, JobType.POLISH, JobStatus.QUEUED)
    _job(db_session, phrase_id, JobType.TTS, JobStatus.RUNNING)

    repo.write_text(
        phrase_id, phrase("He glared again."), POSITION, earned_section=CandidateSection.READY,
    )

    assert _jobs(db_session, phrase_id) == {
        "meaning": ("queued", 1), "media": ("queued", 1), "polish": ("queued", 1),
        "tts": ("running", 0),
    }


def test_set_shown_keeps_the_choice(repo: SqlaOccurrenceRepository) -> None:
    phrase_id = repo.add(replace(
        make_occurrence("He glared at me.", candidate_id=WORD), choice=CardChoice.SKIP,
    )).id
    assert phrase_id is not None

    repo.set_shown([phrase_id], ShownBy.USER)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert (stored.shown_by, stored.choice) == (ShownBy.USER, CardChoice.SKIP)
    repo.set_shown([phrase_id], None)
    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.shown_by is None


def test_the_decision_phrases_are_the_cards_whose_choice_decides(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    second = _added(repo)
    db_session.execute(text("UPDATE phrases SET choice = 'cloze' WHERE id = :id"), {"id": second})
    db_session.expire_all()

    [decision] = repo.decision_phrases([WORD]).values()

    assert decision.id == second
    assert decision.choice is CardChoice.CLOZE


def test_by_source_attaches_results_export_and_active_job(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    SqlaCandidateMeaningRepository(
        db_session, SessionChangeRecorder(db_session),
    ).upsert_for_phrase(phrase_id, CandidateMeaning(
        candidate_id=WORD, meaning="to look angrily", translation=None, synonyms=None,
        examples=None, ipa="/ɡleə/", generated_at=None,
    ))
    db_session.execute(
        text("UPDATE phrases SET choice = 'learn' WHERE id = :id"), {"id": phrase_id},
    )
    bind(db_session, WORD, phrase_id, note_id=NOTE)
    bind(db_session, WORD, WORD_PHRASE, note_id=NOTE, released_at=CREATED_AT)
    db_session.add(JobModel.from_entity(Job.queued(
        JobType.MEANING, SOURCE, WORD, phrase_id=phrase_id, phrase_revision=0,
    )))
    db_session.flush()

    found = {o.id: o for o in repo.by_source(SOURCE)}

    assert set(found) == {WORD_PHRASE, phrase_id}
    stored = found[phrase_id]
    assert stored.meaning is not None
    assert (stored.meaning.meaning, stored.meaning.ipa) == ("to look angrily", "/ɡleə/")
    assert (stored.has_active_job, stored.has_results) == (True, True)
    assert stored.binding is not None
    assert stored.binding.note_kind is NoteKind.LEARN
    plain = found[WORD_PHRASE]
    assert (plain.binding, plain.has_active_job, plain.has_results) == (None, False, False), (
        "a released binding is not in Anki"
    )


def test_projection_is_light_and_marks_what_matters(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    SqlaCandidateClozeRepository(
        db_session, SessionChangeRecorder(db_session),
    ).upsert_for_phrase(phrase_id, CandidateCloze(
        candidate_id=WORD, hidden_word_indices=(1,), hint_kind=ClozeHintKind.NONE,
        custom_hint=None, phrase="He glared at me.",
    ))

    rows = {row.id: row for row in repo.projection(SOURCE)}

    assert rows[phrase_id] == OccurrenceRow(
        id=phrase_id, candidate_id=WORD, key=OccurrenceKey(block=1, line=0, char=3),
        origin=rows[phrase_id].origin, shown_by=None, choice=CardChoice.NONE,
        revision=0, edited_by_user=False, generation=PhraseGeneration(cloze=True),
        binding=None, has_active_job=False,
        text_hash=OccurrenceRow.hash_text("He glared at me."),
        fragment_score=None, shows_polish=False,
        phrase_hash=OccurrenceRow.hash_phrase(phrase("He glared at me."), POSITION),
        source_phrase=phrase("He glared at me."), shown_phrase=phrase("He glared at me."),
        earned_section=rows[phrase_id].earned_section,
    )
    assert not rows[WORD_PHRASE].generation.any
    assert [row.candidate_id for row in repo.projection(OTHER_SOURCE)] == [OTHER_WORD]


def test_projection_carries_the_active_binding_only(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    db_session.execute(
        text("UPDATE phrases SET choice = 'cloze' WHERE id = :id"), {"id": phrase_id},
    )
    bind(db_session, WORD, phrase_id, note_id=NOTE, kind="cloze")
    bind(db_session, WORD, WORD_PHRASE, note_id=NOTE, released_at=CREATED_AT)
    db_session.flush()

    rows = {row.id: row for row in repo.projection(SOURCE)}

    bound = rows[phrase_id].binding
    assert bound is not None
    assert bound.note_kind is NoteKind.CLOZE
    assert rows[WORD_PHRASE].binding is None
    assert [row.id for row in repo.projection(SOURCE)].count(phrase_id) == 1


def test_shown_by_word_keeps_only_shown_phrases(repo: SqlaOccurrenceRepository) -> None:
    hidden = _added(repo)

    shown = repo.shown_by_word(SOURCE)

    assert [o.id for o in shown[WORD]] == [WORD_PHRASE]
    assert hidden not in [o.id for o in shown[WORD]]


def test_get_of_a_missing_phrase_is_none(repo: SqlaOccurrenceRepository) -> None:
    assert repo.get(9999) is None


def test_a_phrase_can_be_marked_as_replacing_the_selection_card(
    repo: SqlaOccurrenceRepository,
) -> None:
    phrase_id = _added(repo)

    repo.set_replaces_selection(phrase_id, replaces=True)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.replaces_selection
    rows = {row.id: row for row in repo.projection(SOURCE)}
    assert rows[phrase_id].replaces_selection
    assert not rows[WORD_PHRASE].replaces_selection
