from __future__ import annotations

import pytest
from backend.application.source_intake.document_normalizer import DocumentNormalizer
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.content import BookContent, Chapter, SubtitlesContent
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer

NORMALIZER = DocumentNormalizer(RegexTextCleaner(), SlangNormalizer())


def _flow(*lines: Line) -> Paragraph:
    return Paragraph(lines=lines, mode=ParagraphMode.FLOW)


@pytest.mark.unit
class TestDocumentNormalizer:
    def test_cleans_lines_and_keeps_their_time(self) -> None:
        content = SubtitlesContent(
            title=None,
            document=Document((
                _flow(Line("  I  gotta ♪ go,  gonna be late", 0, 900), Line("♪ ♪", 900, 1000)),
            )),
        )
        normalized = NORMALIZER.normalize(content)
        assert normalized == SubtitlesContent(
            title=None,
            document=Document((_flow(Line("I gotta go, gonna be late", 0, 900)),)),
        )

    def test_drops_blocks_left_without_text(self) -> None:
        content = SubtitlesContent(
            title=None,
            document=Document((
                Heading(2, "[Chorus]"),
                ListItem(lines=(Line("[Verse 1]"),), ordered=False, depth=0),
                _flow(Line("I wanna stay")),
            )),
        )
        normalized = NORMALIZER.normalize(content)
        assert isinstance(normalized, SubtitlesContent)
        assert normalized.document == Document((_flow(Line("I want to stay")),))

    def test_drops_empty_chapters_of_a_book(self) -> None:
        book = BookContent(
            title="B",
            chapters=(
                Chapter("Empty", Document((_flow(Line("♪")),))),
                Chapter("Full", Document((_flow(Line("Text")),))),
            ),
        )
        normalized = NORMALIZER.normalize(book)
        assert isinstance(normalized, BookContent)
        assert [chapter.title for chapter in normalized.chapters] == ["Full"]

    def test_nothing_left_is_an_error(self) -> None:
        with pytest.raises(InvalidSourceInputError):
            NORMALIZER.normalize(
                SubtitlesContent(title=None, document=Document((_flow(Line("[Music]")),)))
            )
