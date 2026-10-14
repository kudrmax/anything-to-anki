"""A processed source's phrases know where their target stands: block, line, character."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextResponse,
    OccurrenceDTO,
    OccurrenceKeyDTO,
    WordDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.models import PhraseModel
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from sqlalchemy import select

from tests.candidate_sorter_support import threshold_resolver
from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

TEXT = "The sun was low. A glare hit the glass."
DOCUMENT = Document((Paragraph(lines=(Line(TEXT),), mode=ParagraphMode.FLOW),))
GLARE_AT = TEXT.index("glare")
SENTENCE_AT = TEXT.index("A glare")


@pytest.mark.integration
def test_processed_source_phrases_have_a_key(db_session: Session, source_id: int) -> None:
    sentence = TEXT[SENTENCE_AT:]
    analyze_text = MagicMock()
    analyze_text.execute.return_value = AnalyzeTextResponse(
        text=TEXT,
        words=[WordDTO(
            lemma="glare", pos="NOUN", cefr_level="C1", zipf_frequency=3.0,
            occurrences=[OccurrenceDTO(
                phrase=phrase(sentence, "glare"),
                phrase_position=DocumentPositionDTO(
                    block=0, start_line=0, start_char=SENTENCE_AT,
                    end_line=0, end_char=len(TEXT),
                ),
                key=OccurrenceKeyDTO(block=0, line=0, char=GLARE_AT),
                fragment_score=1.0,
            )],
        )],
        total_tokens=10,
        unique_lemmas=9,
    )
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = Source(
        id=source_id, status=SourceStatus.PROCESSING, format=Format.PLAIN, kind=Kind.TEXT,
    )
    settings_repo = MagicMock()
    settings_repo.get.return_value = "B1"
    known_word_repo = MagicMock()
    known_word_repo.get_all_pairs.return_value = set()
    document_repo = MagicMock()
    document_repo.get.return_value = DOCUMENT
    ProcessSourceUseCase(
        source_repo=source_repo,
        candidate_repo=SqlaCandidateRepository(db_session),
        vocabulary=user_vocabulary(known_word_repo),
        settings_repo=settings_repo,
        threshold_resolver=threshold_resolver(settings_repo),
        analyze_text_use_case=analyze_text,
        document_repo=document_repo,
    ).execute(source_id)

    phrases = list(db_session.scalars(select(PhraseModel)))
    assert [(p.block, p.line, p.char) for p in phrases] == [(0, 0, GLARE_AT)]
    assert phrases[0].fragment_score == 1.0
