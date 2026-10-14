"""Until the read side knows phrases, a word is seen as one card: its primary phrase.

TRANSITIONAL(words-phrases): removed in Task 10
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.phrase_origin_kind import (
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.source_role import SourceRole
from backend.infrastructure.persistence.models import (
    PhraseModel,
    SourceModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

POSITION = DocumentPosition(block=0, start_line=0, start_char=0, end_line=0, end_char=10)


def _candidate(
    source_id: int,
    lemma: str,
    text: str,
    *,
    status: CandidateStatus = CandidateStatus.PENDING,
    position: DocumentPosition | None = POSITION,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id, lemma=lemma, pos="VERB", cefr_level="B2", zipf_frequency=3.0,
        source_phrase=phrase(text, lemma), occurrences=1, status=status,
        phrase_position=position,
    )


def _phrases(session: Session, word_id: int) -> list[PhraseModel]:
    return list(session.scalars(
        select(PhraseModel).where(PhraseModel.candidate_id == word_id).order_by(PhraseModel.id)
    ))


def test_a_new_card_is_a_word_with_one_phrase(db_session: Session, source_id: int) -> None:
    repo = SqlaCandidateRepository(db_session)

    created = repo.create_batch([_candidate(source_id, "glare", "he glare at me")])[0]

    assert created.id is not None
    phrases = _phrases(db_session, created.id)
    assert [(p.origin, p.shown_by) for p in phrases] == [("auto", "selection")]
    assert created.source_phrase.text == "he glare at me"


def test_a_card_of_an_existing_word_becomes_its_manual_phrase(
    db_session: Session, source_id: int,
) -> None:
    repo = SqlaCandidateRepository(db_session)
    first = repo.create_batch([_candidate(source_id, "glare", "he glare at me")])[0]

    second = repo.create_batch([_candidate(source_id, "Glare", "they glare")])[0]

    assert second.id == first.id
    words = db_session.scalars(select(StoredCandidateModel)).all()
    assert len(words) == 1
    assert first.id is not None
    phrases = _phrases(db_session, first.id)
    assert [(p.origin, p.shown_by) for p in phrases] == [
        (OccurrenceOrigin.AUTO.value, ShownBy.SELECTION.value),
        (OccurrenceOrigin.MANUAL.value, ShownBy.USER.value),
    ]


def test_skip_skips_the_primary_phrase_and_keeps_the_word_pending(
    db_session: Session, source_id: int,
) -> None:
    repo = SqlaCandidateRepository(db_session)
    word = repo.create_batch([_candidate(source_id, "glare", "he glare at me")])[0]
    assert word.id is not None

    [primary] = _phrases(db_session, word.id)
    SqlaOccurrenceRepository(db_session).set_skipped(primary.id, True)

    model = db_session.get(StoredCandidateModel, word.id)
    assert model is not None
    assert model.status == CandidateStatus.PENDING.value
    assert [p.skipped for p in _phrases(db_session, word.id)] == [True]
    read = repo.get_by_id(word.id)
    assert read is not None
    assert read.status is CandidateStatus.SKIP
    assert repo.count_by_status(CandidateStatus.SKIP) == 1
    assert repo.count_by_status(CandidateStatus.PENDING) == 0


def test_the_phrase_of_the_decision_is_the_one_the_word_is_seen_through(
    db_session: Session, source_id: int,
) -> None:
    repo = SqlaCandidateRepository(db_session)
    word = repo.create_batch([_candidate(source_id, "glare", "he glare at me")])[0]
    repo.create_batch([_candidate(source_id, "glare", "they glare")])
    assert word.id is not None
    manual = _phrases(db_session, word.id)[1]
    manual.is_decision = True
    db_session.flush()

    read = repo.get_by_id(word.id)

    assert read is not None
    assert read.source_phrase.text == "they glare"


def test_phrase_edits_write_through_to_the_primary_phrase(
    db_session: Session, source_id: int,
) -> None:
    repo = SqlaCandidateRepository(db_session)
    word = repo.create_batch([_candidate(source_id, "glare", "he glare at me")])[0]
    assert word.id is not None

    repo.set_polished_phrase(word.id, phrase("he glare", "glare"))
    repo.set_polish_reverted(word.id, True)

    read = repo.get_by_id(word.id)
    assert read is not None
    assert read.polished_phrase is not None
    assert (read.polished_phrase.text, read.polish_reverted) == ("he glare", True)


@pytest.mark.parametrize("role", [SourceRole.TOPIC, SourceRole.SAVED_PHRASES])
def test_a_phrase_of_a_topic_or_saved_phrases_is_collected(
    db_session: Session, role: SourceRole,
) -> None:
    db_session.add(SourceModel(id=5, title="t", status="done", role=role.value))
    db_session.flush()
    repo = SqlaCandidateRepository(db_session)

    word = repo.create_batch([_candidate(5, "glare", "he glare at me", position=None)])[0]

    assert word.id is not None
    assert [(p.origin, p.shown_by) for p in _phrases(db_session, word.id)] == [
        (OccurrenceOrigin.COLLECTED.value, ShownBy.USER.value),
    ]
