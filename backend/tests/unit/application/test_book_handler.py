from __future__ import annotations

import pytest
from backend.application.source_intake.book_handler import (
    SPLIT_OPTION_ID,
    SPLIT_QUESTION_ID,
    WHOLE_OPTION_ID,
    BookHandler,
)
from backend.domain.value_objects.content import BookContent, Chapter, Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Answers

pytestmark = pytest.mark.unit

SPLIT = Answers({SPLIT_QUESTION_ID: SPLIT_OPTION_ID})
WHOLE = Answers({SPLIT_QUESTION_ID: WHOLE_OPTION_ID})
LABEL = "dune.epub"


def _document(text: str) -> Document:
    return Document(blocks=(Paragraph(lines=(Line(text),), mode=ParagraphMode.FLOW),))


def _book(*titles: str | None) -> BookContent:
    chapters = tuple(
        Chapter(title=title, document=_document(f"words of {n}"))
        for n, title in enumerate(titles, 1)
    )
    return BookContent(title="Dune", chapters=chapters)


class TestBookDrafts:
    def test_split_book_is_a_draft_per_chapter(self) -> None:
        drafts = BookHandler().drafts(_book("Desert", None), SPLIT, Format.EPUB, LABEL)

        assert [d.own_title for d in drafts] == ["Desert", "Chapter 2"]
        assert [d.label for d in drafts] == ["chapter 1", "chapter 2"]
        assert {d.kind for d in drafts} == {Kind.BOOK}

    def test_whole_book_is_one_draft_named_after_the_book(self) -> None:
        drafts = BookHandler().drafts(_book("Desert", "Spice"), WHOLE, Format.EPUB, LABEL)

        assert len(drafts) == 1
        assert (drafts[0].own_title, drafts[0].label) == ("Dune", LABEL)
        assert drafts[0].words == 4

    def test_split_question_shows_no_chapter_list(self) -> None:
        (question,) = BookHandler().questions(_book("Desert", "Spice"))

        assert all(option.details is None for option in question.options)
