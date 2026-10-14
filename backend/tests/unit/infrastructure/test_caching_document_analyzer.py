from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.adapters.caching_document_analyzer import (
    CachingDocumentAnalyzer,
    document_hash,
)
from backend.infrastructure.persistence.database import Base, cleanup_parse_cache
from backend.infrastructure.persistence.models import DocumentParseModel
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_parse_cache import SqlaParseCache
from sqlalchemy import StaticPool, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import Generator

VERSION = "3.8.0:3.8.0:1"
NEW_VERSION = "3.8.0:3.8.0:2"


def _document(text_: str) -> Document:
    return Document((Paragraph(lines=(Line(text_),), mode=ParagraphMode.FLOW),))


class _CountingAnalyzer(DocumentAnalyzer):
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, document: Document) -> AnalyzedDocument:
        self.calls += 1
        layout = DocumentLayout(document)
        tokens = [
            TokenData(
                index=0, text="Glare", lemma="glare", pos="NOUN", tag="NN",
                head_index=1, children_indices=(), is_punct=False, is_stop=False,
                is_alpha=True, is_propn=False, sent_index=0, dep="nsubj",
                whitespace_after=" ", char_start=0,
            ),
            TokenData(
                index=1, text="hurts", lemma="hurt", pos="VERB", tag="VBZ",
                head_index=1, children_indices=(0, 2), is_punct=False, is_stop=False,
                is_alpha=True, is_propn=False, sent_index=0, dep="ROOT",
                whitespace_after="", char_start=6,
            ),
            TokenData(
                index=2, text="", lemma=".", pos="PUNCT", tag=".",
                head_index=1, children_indices=(), is_punct=True, is_stop=False,
                is_alpha=False, is_propn=False, sent_index=0, dep="punct",
                whitespace_after="", char_start=11,
            ),
        ]
        return AnalyzedDocument(tokens=tokens, layout=layout)


@pytest.fixture()
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _analyzer(
    session_factory: sessionmaker[Session], inner: DocumentAnalyzer, version: str = VERSION,
) -> CachingDocumentAnalyzer:
    return CachingDocumentAnalyzer(inner, SqlaParseCache(session_factory), version)


@pytest.mark.unit
class TestCachingDocumentAnalyzer:
    def test_same_document_is_parsed_once(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        inner = _CountingAnalyzer()
        analyzer = _analyzer(session_factory, inner)
        document = _document("Glare hurts")

        first = analyzer.analyze(document)
        second = analyzer.analyze(document)

        assert inner.calls == 1
        assert second.tokens == first.tokens
        assert second.layout.text == first.layout.text

    def test_cache_outlives_the_analyzer(self, session_factory: sessionmaker[Session]) -> None:
        document = _document("Glare hurts")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)
        inner = _CountingAnalyzer()

        _analyzer(session_factory, inner).analyze(document)

        assert inner.calls == 0

    def test_new_analyzer_version_parses_again(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        document = _document("Glare hurts")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)
        inner = _CountingAnalyzer()

        _analyzer(session_factory, inner, NEW_VERSION).analyze(document)

        assert inner.calls == 1

    def test_changed_document_parses_again(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        inner = _CountingAnalyzer()
        analyzer = _analyzer(session_factory, inner)

        analyzer.analyze(_document("Glare hurts"))
        analyzer.analyze(_document("Glare hurts a lot"))

        assert inner.calls == 2

    def test_parse_is_stored_compressed(self, session_factory: sessionmaker[Session]) -> None:
        document = _document("Glare hurts")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)

        with session_factory() as session:
            row = session.scalars(select(DocumentParseModel)).one()
        assert row.document_hash == document_hash(document)
        assert row.analyzer_version == VERSION
        assert not row.tokens.startswith(b"[")


@pytest.mark.unit
class TestParseCacheCleanup:
    def test_parse_of_a_document_no_source_has_is_removed(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        live, gone = _document("Glare hurts"), _document("Nobody reads this")
        with session_factory() as session:
            session.execute(text(
                "INSERT INTO sources (id, title, status, created_at)"
                " VALUES (1, 'title', 'done', '2026-01-01 00:00:00')"
            ))
            SqlaDocumentRepository(session).save(1, live)
            session.commit()
        analyzer = _analyzer(session_factory, _CountingAnalyzer())
        analyzer.analyze(live)
        analyzer.analyze(gone)

        cleanup_parse_cache(session_factory)

        with session_factory() as session:
            hashes = set(session.scalars(select(DocumentParseModel.document_hash)))
        assert hashes == {document_hash(live)}
