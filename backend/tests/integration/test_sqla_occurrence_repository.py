"""The phrases of words: storing, rewriting their text and words, marks and results."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import DecisionKind, ShownBy
from backend.infrastructure.persistence.models import (
    AnkiSyncedCardModel,
    JobModel,
    PhraseWordModel,
)
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select

from tests.integration.conftest import insert_source
from tests.phrase_support import make_occurrence, phrase
from tests.word_support import insert_word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE = 1
OTHER_SOURCE = 2
WORD = 10
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
    return SqlaOccurrenceRepository(db_session)


def _words(session: Session, phrase_id: int) -> set[str]:
    return set(session.scalars(
        select(PhraseWordModel.lemma).where(PhraseWordModel.phrase_id == phrase_id)
    ))


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
        polished=phrase("He stared at us"), polish_reverted=True,
    )

    assert _words(db_session, phrase_id) == {"he", "glared", "at", "me"}


def test_write_text_bumps_the_revision_only_when_asked(
    repo: SqlaOccurrenceRepository,
) -> None:
    phrase_id = _added(repo)

    repo.write_text(phrase_id, phrase("He glared."), POSITION)
    repo.write_text(phrase_id, phrase("He glared again."), POSITION, bump_revision=True)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.revision == 1
    assert stored.source_phrase.text == "He glared again."


def test_set_shown_and_skipped(repo: SqlaOccurrenceRepository) -> None:
    phrase_id = _added(repo)

    repo.set_shown([phrase_id], ShownBy.USER)
    repo.set_skipped(phrase_id, True)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert (stored.shown_by, stored.skipped) == (ShownBy.USER, True)
    repo.set_shown([phrase_id], None)
    stored = repo.get(phrase_id)
    assert stored is not None
    assert stored.shown_by is None


def test_set_decision_moves_the_mark_to_one_phrase(repo: SqlaOccurrenceRepository) -> None:
    first = WORD  # the phrase the word was inserted with
    second = _added(repo)

    repo.set_decision(WORD, first, DecisionKind.LEARN)
    repo.set_decision(WORD, second, DecisionKind.CLOZE)

    by_id = {o.id: o for o in repo.by_source(SOURCE)}
    assert (by_id[first].is_decision, by_id[first].decision_kind) == (False, None)
    assert (by_id[second].is_decision, by_id[second].decision_kind) == (True, DecisionKind.CLOZE)
    repo.set_decision(WORD, None, None)
    assert not any(o.is_decision for o in repo.by_source(SOURCE))


def test_by_source_attaches_results_export_and_active_job(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    SqlaCandidateMeaningRepository(db_session).upsert_for_phrase(phrase_id, CandidateMeaning(
        candidate_id=WORD, meaning="to look angrily", translation=None, synonyms=None,
        examples=None, ipa="/ɡleə/", generated_at=None,
    ))
    db_session.add(AnkiSyncedCardModel(candidate_id=WORD, phrase_id=phrase_id, anki_note_id=NOTE))
    db_session.add(JobModel.from_entity(Job.queued(
        JobType.MEANING, SOURCE, WORD, phrase_id=phrase_id, phrase_revision=0,
    )))
    db_session.flush()

    found = {o.id: o for o in repo.by_source(SOURCE)}

    assert set(found) == {WORD, phrase_id}
    stored = found[phrase_id]
    assert stored.meaning is not None
    assert (stored.meaning.meaning, stored.meaning.ipa) == ("to look angrily", "/ɡleə/")
    assert (stored.exported, stored.has_active_job, stored.has_results) == (True, True, True)
    plain = found[WORD]
    assert (plain.exported, plain.has_active_job, plain.has_results) == (False, False, False)


def test_projection_is_light_and_marks_what_matters(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    SqlaCandidateClozeRepository(db_session).upsert_for_phrase(phrase_id, CandidateCloze(
        candidate_id=WORD, hidden_word_indices=(1,), hint_kind=ClozeHintKind.NONE,
        custom_hint=None, phrase="He glared at me.",
    ))

    rows = {row.id: row for row in repo.projection(SOURCE)}

    assert rows[phrase_id] == OccurrenceRow(
        id=phrase_id, candidate_id=WORD, key=OccurrenceKey(block=1, line=0, char=3),
        origin=rows[phrase_id].origin, shown_by=None, skipped=False, is_decision=False,
        revision=0, edited_by_user=False, has_results=True, exported=False,
        has_active_job=False, text_hash=OccurrenceRow.hash_text("He glared at me."),
    )
    assert not rows[WORD].has_results
    assert [row.candidate_id for row in repo.projection(OTHER_SOURCE)] == [OTHER_WORD]


def test_reset_results_drops_everything_made_for_the_phrase(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    phrase_id = _added(repo)
    repo.write_text(
        phrase_id, phrase("He glared at me."), POSITION, polished=phrase("He stared at us"),
    )
    SqlaCandidateMeaningRepository(db_session).upsert_for_phrase(phrase_id, CandidateMeaning(
        candidate_id=WORD, meaning="m", translation=None, synonyms=None, examples=None,
        ipa=None, generated_at=None,
    ))

    repo.reset_results(phrase_id)

    stored = repo.get(phrase_id)
    assert stored is not None
    assert (stored.polished_phrase, stored.meaning, stored.has_results) == (None, None, False)
    assert _words(db_session, phrase_id) == {"he", "glared", "at", "me"}


def test_shown_by_word_keeps_only_shown_phrases(repo: SqlaOccurrenceRepository) -> None:
    hidden = _added(repo)

    shown = repo.shown_by_word(SOURCE)

    assert [o.id for o in shown[WORD]] == [WORD]
    assert hidden not in [o.id for o in shown[WORD]]


def test_get_of_a_missing_phrase_is_none(repo: SqlaOccurrenceRepository) -> None:
    assert repo.get(9999) is None
