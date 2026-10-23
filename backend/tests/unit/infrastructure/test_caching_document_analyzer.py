from __future__ import annotations

import tracemalloc
import zlib
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
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
BOOK_TOKENS = 60_000
# How much memory storing or reading a parse may take on top of its tokens, as a share of
# what the tokens take: the parse is never held whole as rows or as one JSON text.
MEMORY_OVER_TOKENS = 0.25
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


def _book_tokens() -> list[TokenData]:
    return [
        TokenData(
            index=i, text=f"wörd\n{i}", lemma=f"word{i % 50}", pos="NOUN", tag="NN",
            head_index=max(i - 1, 0), children_indices=(i + 1,) if i % 2 else (),
            is_punct=False, is_stop=bool(i % 3), is_alpha=True, is_propn=False,
            sent_index=i // 20, dep="nsubj", whitespace_after=" ", char_start=i * 7,
        )
        for i in range(BOOK_TOKENS)
    ]


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


    def test_old_version_of_a_parse_is_dropped_when_a_new_one_is_stored(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        document, other = _document("Glare hurts"), _document("Other text")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)
        _analyzer(session_factory, _CountingAnalyzer()).analyze(other)

        _analyzer(session_factory, _CountingAnalyzer(), NEW_VERSION).analyze(document)

        with session_factory() as session:
            rows = {
                (row.document_hash, row.analyzer_version)
                for row in session.scalars(select(DocumentParseModel))
            }
        assert rows == {
            (document_hash(document), NEW_VERSION), (document_hash(other), VERSION),
        }

    def test_parse_of_a_book_round_trips(self, session_factory: sessionmaker[Session]) -> None:
        tokens = _book_tokens()
        cache = SqlaParseCache(session_factory)

        cache.put("book", VERSION, tokens)

        assert cache.get("book", VERSION) == tokens

    def test_parse_of_a_book_is_stored_and_read_without_a_copy_of_it_in_memory(
        self, session_factory: sessionmaker[Session],
    ) -> None:
        cache = SqlaParseCache(session_factory)
        tracemalloc.start()
        try:
            tokens = _book_tokens()
            held = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
            cache.put("book", VERSION, tokens)
            put_extra = tracemalloc.get_traced_memory()[1] - held
            del tokens
            before_get = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
            read = cache.get("book", VERSION)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert read is not None
        assert put_extra < held * MEMORY_OVER_TOKENS
        assert peak - current < (current - before_get) * MEMORY_OVER_TOKENS

    def test_cut_short_parse_is_a_miss(self, session_factory: sessionmaker[Session]) -> None:
        document = _document("Glare hurts")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)
        with session_factory() as session:
            row = session.scalars(select(DocumentParseModel)).one()
            row.tokens = row.tokens[: len(row.tokens) // 2]
            session.commit()

        assert SqlaParseCache(session_factory).get(document_hash(document), VERSION) is None

    @pytest.mark.parametrize("broken", [b"not zlib", zlib.compress(b"not json")])
    def test_unreadable_parse_is_parsed_again_and_replaced(
        self, session_factory: sessionmaker[Session], broken: bytes,
    ) -> None:
        document = _document("Glare hurts")
        _analyzer(session_factory, _CountingAnalyzer()).analyze(document)
        with session_factory() as session:
            session.scalars(select(DocumentParseModel)).one().tokens = broken
            session.commit()
        inner = _CountingAnalyzer()

        analyzed = _analyzer(session_factory, inner).analyze(document)
        cached = _analyzer(session_factory, _CountingAnalyzer()).analyze(document)

        assert inner.calls == 1
        assert cached.tokens == analyzed.tokens


@pytest.mark.unit
class TestDocumentHash:
    def test_paragraph_of_lines_and_flowing_text_are_different_inputs(self) -> None:
        text_ = "Glare hurts"
        lines = Document((Paragraph(lines=(Line(text_),), mode=ParagraphMode.LINES),))
        flow = Document((Paragraph(lines=(Line(text_),), mode=ParagraphMode.FLOW),))
        heading = Document((Heading(1, text_),))

        assert len({document_hash(lines), document_hash(flow), document_hash(heading)}) == 3

    def test_same_document_has_the_same_hash(self) -> None:
        assert document_hash(_document("Glare hurts")) == document_hash(_document("Glare hurts"))


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
