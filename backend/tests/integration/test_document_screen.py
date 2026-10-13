"""The source screen: the document with its marks, and phrases selected anew on it."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.get_source_document import GetSourceDocumentUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import InvalidPhraseError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.document_position import DocumentPosition
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

DOCUMENT = Document((
    Heading(1, "Title"),
    Paragraph(
        (Line("He gave up the relentless pursuit"), Line("of happiness.")), ParagraphMode.FLOW,
    ),
))


def _candidate(source_id: int, lemma: str, target: DocumentPosition) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id, lemma=lemma, pos="NOUN", cefr_level="B2", zipf_frequency=3.0,
        context_fragment="He gave up the relentless pursuit of happiness.",
        fragment_purity="clean", occurrences=1, status=CandidateStatus.PENDING,
        phrase_position=DocumentPosition(1, 0, 0, 1, 13), target_position=target,
    )


def test_marks_that_would_overlap_keep_the_first(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    give_up, give, pursuit = SqlaCandidateRepository(db_session).create_batch([
        _candidate(source_id, "give up", DocumentPosition(1, 0, 3, 0, 10)),
        _candidate(source_id, "give", DocumentPosition(1, 0, 3, 0, 7)),
        _candidate(source_id, "pursuit", DocumentPosition(1, 0, 26, 0, 33)),
    ])

    screen = GetSourceDocumentUseCase(
        SqlaDocumentRepository(db_session), SqlaCandidateRepository(db_session),
    ).execute(source_id)

    assert [b.type for b in screen.blocks] == ["heading", "paragraph"]
    assert [line.text for line in screen.blocks[1].lines] == [
        "He gave up the relentless pursuit", "of happiness.",
    ]
    assert [h.candidate_id for h in screen.highlights] == [give_up.id, pursuit.id]
    assert give.id not in {h.candidate_id for h in screen.highlights}


def test_selected_phrase_replaces_the_old_one(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = SqlaCandidateRepository(db_session).create_batch([
        _candidate(source_id, "pursuit", DocumentPosition(1, 0, 26, 0, 33)),
    ])
    assert candidate.id is not None
    set_boundary = SetPhraseBoundaryUseCase(
        SqlaCandidateRepository(db_session), SqlaDocumentRepository(db_session),
    )

    phrase = set_boundary.execute(candidate.id, SelectionDTO(
        start_block=1, start_line=0, start_char=14, end_block=1, end_line=1, end_char=13,
    ))

    assert phrase == "relentless pursuit\nof happiness."
    updated = SqlaCandidateRepository(db_session).get_by_id(candidate.id)
    assert updated is not None
    assert updated.context_fragment == phrase
    assert updated.phrase_position == DocumentPosition(1, 0, 15, 1, 13)
    assert updated.target_position == DocumentPosition(1, 0, 26, 0, 33)


def test_selection_across_blocks_is_rejected(db_session: Session, source_id: int) -> None:
    SqlaDocumentRepository(db_session).save(source_id, DOCUMENT)
    (candidate,) = SqlaCandidateRepository(db_session).create_batch([
        _candidate(source_id, "pursuit", DocumentPosition(1, 0, 26, 0, 33)),
    ])
    assert candidate.id is not None
    with pytest.raises(InvalidPhraseError, match="one paragraph"):
        SetPhraseBoundaryUseCase(
            SqlaCandidateRepository(db_session), SqlaDocumentRepository(db_session),
        ).execute(candidate.id, SelectionDTO(
            start_block=0, start_line=0, start_char=0, end_block=1, end_line=0, end_char=5,
        ))
