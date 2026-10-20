"""The source screen: the document with its marks, and phrases selected anew on it."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.get_review_documents import GetReviewDocumentsUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.stored_candidate import StoredCandidate
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
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.models import CollectionModel, SourceModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

from tests.candidate_sorter_support import section_stamper
from tests.lock_support import free_lock
from tests.phrase_support import phrase, shown_lemmas
from tests.source_order_support import added_order
from tests.word_support import CardSeed, store_cards

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


def _candidate(source_id: int, lemma: str, target: str) -> CardSeed:
    return CardSeed(
        StoredCandidate(
            source_id=source_id,
            lemma=lemma,
            pos="NOUN",
            cefr_level="B2",
            zipf_frequency=3.0,
            occurrences=1,
            status=WordStatus.NEW,
        ),
        phrase(PHRASE, target),
        position=DocumentPosition(1, 0, 0, 1, 13),
    )


def _screen(session: Session) -> GetReviewDocumentsUseCase:
    return GetReviewDocumentsUseCase(
        SourceScopeResolver(
            SqlaSourceRepository(session), SqlaCollectionRepository(session), added_order(),
        ),
        SqlaDocumentRepository(session), SqlaCardQuery(session),
    )


COLLECTION, FIRST, SECOND, TOPIC = 7, 1, 2, 3


def _phrases_of(session: Session, source_id: int) -> set[int]:
    return {place.phrase_id for place in SqlaCardQuery(session).shown_places(source_id)}


def test_documents_of_a_collection_in_set_order(db_session: Session) -> None:
    db_session.add(CollectionModel(id=COLLECTION, name="Show"))
    db_session.add_all([
        SourceModel(
            id=FIRST, title="Pilot", status="done", collection_id=COLLECTION,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        SourceModel(
            id=SECOND, title="Episode 2", status="done", collection_id=COLLECTION,
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        SourceModel(
            id=TOPIC, title="Salary talk", status="done", collection_id=COLLECTION,
            role="topic", created_at=datetime(2026, 1, 3, tzinfo=UTC),
        ),
    ])
    db_session.flush()
    for source_id in (FIRST, SECOND):
        SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
        store_cards(db_session, [_candidate(source_id, "pursuit", "pursuit")])

    docs = _screen(db_session).execute(SourceScope.collection(COLLECTION))

    assert [(d.source_id, d.title) for d in docs] == [(SECOND, "Episode 2"), (FIRST, "Pilot")]
    assert all(
        h.phrase_id in _phrases_of(db_session, d.source_id) for d in docs for h in d.highlights
    )
    assert all(d.highlights for d in docs)


def test_marks_that_would_overlap_keep_the_first(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    give_up, give, pursuit = store_cards(db_session, [
        _candidate(source_id, "give up", "gave up"),
        _candidate(source_id, "give", "gave"),
        _candidate(source_id, "pursuit", "pursuit"),
    ])

    [screen] = _screen(db_session).execute(SourceScope.source(source_id))

    assert [b.type for b in screen.blocks] == ["heading", "paragraph"]
    assert [line.text for line in screen.blocks[1].lines] == [
        "He gave up the relentless pursuit", "of happiness.",
    ]
    assert [h.word_id for h in screen.highlights] == [give_up.word_id, pursuit.word_id]
    assert give.word_id not in {h.word_id for h in screen.highlights}


def test_selected_phrase_replaces_the_old_one(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        _candidate(source_id, "pursuit", "pursuit"),
    ])

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
    assert shown_lemmas(db_session, updated.id) == {"relentless", "pursuit", "of", "happiness"}


def test_an_example_put_in_the_document_gets_its_key(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        replace(_candidate(source_id, "pursuit", "pursuit"), position=None),
    ])

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
        section_stamper(SqlaSettingsRepository(db_session)),
        MagicMock(),
    )


def test_selection_across_blocks_is_rejected(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = store_cards(db_session, [
        _candidate(source_id, "pursuit", "pursuit"),
    ])
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


def _rated(seed: CardSeed, level: CEFRLevel) -> CardSeed:
    return replace(seed, word=replace(seed.word, cefr_breakdown=_breakdown(level)))


def test_a_mark_has_the_level_of_its_stored_breakdown(
    db_session: Session, source_id: int,
) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    rated, unrated, unknown = store_cards(db_session, [
        _rated(_candidate(source_id, "pursuit", "pursuit"), CEFRLevel.C1),
        _candidate(source_id, "give up", "gave up"),
        _rated(_candidate(source_id, "happiness", "happiness"), CEFRLevel.UNKNOWN),
    ])

    levels = {p.word_id: p.cefr_level for p in SqlaCardQuery(db_session).shown_places(source_id)}

    assert levels == {rated.word_id: "C1", unrated.word_id: None, unknown.word_id: None}
