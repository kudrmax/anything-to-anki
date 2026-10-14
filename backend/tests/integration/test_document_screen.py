"""The source screen: the document with its marks, and phrases selected anew on it."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.get_source_document import GetSourceDocumentUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.exceptions import InvalidPhraseError
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.models import PhraseWordModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select

from tests.lock_support import free_lock
from tests.phrase_support import phrase
from tests.word_support import SeedWord, store_cards

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

DOCUMENT = Document((
    Heading(1, "Title"),
    Paragraph(
        (Line("He gave up the relentless pursuit"), Line("of happiness.")), ParagraphMode.FLOW,
    ),
))


PHRASE = "He gave up the relentless pursuit of happiness."


def _candidate(source_id: int, lemma: str, target: str) -> SeedWord:
    return SeedWord(
        source_id=source_id, lemma=lemma, pos="NOUN", cefr_level="B2", zipf_frequency=3.0,
        source_phrase=phrase(PHRASE, target),
        occurrences=1, status=WordStatus.PENDING,
        phrase_position=DocumentPosition(1, 0, 0, 1, 13),
    )


def test_marks_that_would_overlap_keep_the_first(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    give_up, give, pursuit = store_cards(db_session, [
        _candidate(source_id, "give up", "gave up"),
        _candidate(source_id, "give", "gave"),
        _candidate(source_id, "pursuit", "pursuit"),
    ])

    screen = GetSourceDocumentUseCase(
        SqlaDocumentRepository(db_session), SqlaCardQuery(db_session),
    ).execute(source_id)

    assert [b.type for b in screen.blocks] == ["heading", "paragraph"]
    assert [line.text for line in screen.blocks[1].lines] == [
        "He gave up the relentless pursuit", "of happiness.",
    ]
    assert [h.word_id for h in screen.highlights] == [give_up.id, pursuit.id]
    assert give.id not in {h.word_id for h in screen.highlights}


def test_selected_phrase_replaces_the_old_one(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        _candidate(source_id, "pursuit", "pursuit"),
    ])
    assert candidate.phrase_id is not None

    text = _set_boundary(db_session).execute(candidate.phrase_id, SelectionDTO(
        start_block=1, start_line=0, start_char=14, end_block=1, end_line=1, end_char=13,
    ))

    assert text == "relentless pursuit of happiness."
    updated = SqlaOccurrenceRepository(db_session).get(candidate.phrase_id)
    assert updated is not None
    assert updated.source_phrase.text == text
    assert updated.source_phrase.target_text() == "pursuit"
    assert updated.phrase_position == DocumentPosition(1, 0, 15, 1, 13)
    assert updated.edited_by_user
    assert updated.key == OccurrenceKey(block=1, line=0, char=PHRASE.index("pursuit"))
    assert set(db_session.scalars(
        select(PhraseWordModel.lemma).where(PhraseWordModel.phrase_id == updated.id)
    )) == {"relentless", "pursuit", "of", "happiness"}


def test_an_example_put_in_the_document_gets_its_key(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        replace(_candidate(source_id, "pursuit", "pursuit"), phrase_position=None),
    ])
    assert candidate.phrase_id is not None

    _set_boundary(db_session).execute(candidate.phrase_id, SelectionDTO(
        start_block=1, start_line=0, start_char=14, end_block=1, end_line=1, end_char=13,
    ))

    updated = SqlaOccurrenceRepository(db_session).get(candidate.phrase_id)
    assert updated is not None
    assert updated.key == OccurrenceKey(block=1, line=0, char=PHRASE.index("pursuit"))


def _set_boundary(db_session: Session) -> SetPhraseBoundaryUseCase:
    return SetPhraseBoundaryUseCase(
        SqlaOccurrenceRepository(db_session), SqlaCandidateRepository(db_session),
        SqlaDocumentRepository(db_session), Container().phrase_reader, free_lock(),
    )


def test_selection_across_blocks_is_rejected(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        _candidate(source_id, "pursuit", "pursuit"),
    ])
    assert candidate.phrase_id is not None
    with pytest.raises(InvalidPhraseError, match="one paragraph"):
        _set_boundary(db_session).execute(candidate.phrase_id, SelectionDTO(
            start_block=0, start_line=0, start_char=0, end_block=1, end_line=0, end_char=5,
        ))


def _breakdown(level: CEFRLevel) -> CEFRBreakdown:
    vote = SourceVote(
        source_name="Cambridge Dictionary", distribution={level: 1.0}, top_level=level,
    )
    return CEFRBreakdown(
        final_level=level, decision_method="priority", priority_votes=[vote], votes=[],
    )


def test_a_mark_has_the_level_of_its_stored_breakdown(
    db_session: Session, source_id: int,
) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    rated, unrated, unknown = store_cards(db_session, [
        replace(
            _candidate(source_id, "pursuit", "pursuit"), cefr_breakdown=_breakdown(CEFRLevel.C1),
        ),
        _candidate(source_id, "give up", "gave up"),
        replace(
            _candidate(source_id, "happiness", "happiness"),
            cefr_breakdown=_breakdown(CEFRLevel.UNKNOWN),
        ),
    ])

    levels = {p.word_id: p.cefr_level for p in SqlaCardQuery(db_session).shown_places(source_id)}

    assert levels == {rated.id: "C1", unrated.id: None, unknown.id: None}
