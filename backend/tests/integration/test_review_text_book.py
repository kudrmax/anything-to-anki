"""A whole book as one source: after its first read, a chunk of its text is read without
laying out the document again, in at most CHUNK_READ_SECONDS."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from backend.application.utils.open_review import OpenReview
from backend.application.utils.review_text import ReviewText
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.application.utils.source_texts import SourceTexts
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.review_order import ReviewOrder
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.models import dump_phrase, dump_position
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_card_state_query import SqlaCardStateQuery
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.source_order_support import added_order
from tests.word_support import CREATED_AT, TEST_SECTION

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

BOOK = 1
BLOCKS = 10_000
# Each block opens with the sentence of its cards, then runs on to about 250 characters:
# 2.5 million characters in all, a long book.
SENTENCE = "He gave up the relentless pursuit of happiness."
FILLER = " And the rain kept falling on the quiet town all through the night."
BLOCK_TEXT = SENTENCE + FILLER * 3
CARDS_PER_BLOCK = 2
TARGETS = ("gave up", "pursuit")
CHUNK_READ_SECONDS = 0.150


def _book() -> Document:
    return Document(tuple(
        Paragraph((Line(BLOCK_TEXT), Line(f"Line {index}.")), ParagraphMode.FLOW)
        for index in range(BLOCKS)
    ))


@pytest.fixture()
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """A database file with the book and two shown cards in each of its blocks."""
    engine = create_engine(f"sqlite:///{tmp_path / 'book.db'}")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    with made() as session:
        insert_source(session, BOOK)
        SqlaDocumentRepository(session).save(BOOK, _book())
        phrases = [dump_phrase(phrase(SENTENCE, target)) for target in TARGETS]
        words = range(1, BLOCKS * CARDS_PER_BLOCK + 1)
        session.execute(text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
            " is_sweet_spot, occurrences, is_phrasal_verb)"
            " VALUES (:id, :source, :lemma, 'NOUN', 3.0, 0, 1, 0)"
        ), [{"id": w, "source": BOOK, "lemma": f"word{w}"} for w in words])
        session.execute(text(
            "INSERT INTO phrases (id, candidate_id, block, source_phrase, phrase_position,"
            " origin, shown_by, choice, created_at, earned_section)"
            " VALUES (:id, :id, :block, :phrase, :position, 'auto', 'selection', 'none',"
            " :created_at, :section)"
        ), [
            {
                "id": w, "block": (w - 1) // CARDS_PER_BLOCK,
                "phrase": phrases[(w - 1) % CARDS_PER_BLOCK],
                "position": dump_position(_sentence_at((w - 1) // CARDS_PER_BLOCK)),
                "created_at": CREATED_AT, "section": TEST_SECTION,
            }
            for w in words
        ])
        session.commit()
    yield made
    engine.dispose()


def _sentence_at(block: int) -> DocumentPosition:
    return DocumentPosition(block, 0, 0, 0, len(SENTENCE))


def _resolver(session: Session) -> SourceScopeResolver:
    return SourceScopeResolver(
        SqlaSourceRepository(session, SessionChangeRecorder(session)),
        SqlaCollectionRepository(session),
        added_order(),
    )


def _review() -> OpenReview:
    return OpenReview(
        scope_token=f"source-{BOOK}", source_ids=frozenset({BOOK}),
        sort=CandidateSortOrder.RELEVANCE, step=None,
        order=ReviewOrder((), sectioned=False), opened=frozenset(), current=None,
    )


def test_a_chunk_of_a_whole_book_read_again_is_read_quickly(
    factory: sessionmaker[Session],
) -> None:
    texts = SourceTexts()
    review = _review()

    def read(block: int) -> tuple[float, int]:
        with factory() as session:
            reader = ReviewText(
                _resolver(session), SqlaDocumentRepository(session), SqlaCardQuery(session),
                SqlaCardStateQuery(session), texts,
            )
            started = time.perf_counter()
            chunk = reader.chunk(review, BOOK, block)
            return time.perf_counter() - started, len(chunk.highlights)

    read(0)
    seconds, marks = read(BLOCKS // 2)

    assert marks > 0
    assert seconds <= CHUNK_READ_SECONDS, f"{seconds * 1000:.0f} ms"
