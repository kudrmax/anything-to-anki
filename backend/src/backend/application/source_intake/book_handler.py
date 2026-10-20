from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.source_intake.kind_handler import KindHandler
from backend.application.source_intake.source_draft import SourceDraft
from backend.domain.services.word_count import count_words
from backend.domain.value_objects.content import BookContent, Kind
from backend.domain.value_objects.document import Document
from backend.domain.value_objects.question import Question, QuestionOption

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers

SPLIT_QUESTION_ID = "book.split"
SPLIT_OPTION_ID = "split"
WHOLE_OPTION_ID = "whole"
UNTITLED_BOOK = "Book"


class BookHandler(KindHandler):
    """A book becomes a source per chapter or one source; a book of several chapters asks
    which."""

    @property
    def kind(self) -> Kind:
        return Kind.BOOK

    @staticmethod
    def book_name(content: Content) -> str:
        return _book(content).title or UNTITLED_BOOK

    def questions(self, content: Content) -> tuple[Question, ...]:
        book = _book(content)
        if len(book.chapters) < 2:
            return ()
        counts = [count_words(chapter.document.text) for chapter in book.chapters]
        split = QuestionOption(
            id=SPLIT_OPTION_ID,
            label=f"{len(counts)} chapters · {_word_range(counts)} each",
        )
        whole = QuestionOption(id=WHOLE_OPTION_ID, label=f"One source · {_words(sum(counts))}")
        return (
            Question(
                id=SPLIT_QUESTION_ID,
                prompt=f"Add «{self.book_name(book)}» as",
                options=(split, whole),
                default=SPLIT_OPTION_ID,
            ),
        )

    def drafts(
        self, content: Content, answers: Answers, source_format: Format, label: str,
    ) -> tuple[SourceDraft, ...]:
        book = _book(content)
        if len(book.chapters) > 1 and answers.get(SPLIT_QUESTION_ID) == SPLIT_OPTION_ID:
            return tuple(
                _draft(
                    chapter.document, chapter.title or f"Chapter {number}",
                    f"chapter {number}", source_format,
                )
                for number, chapter in enumerate(book.chapters, start=1)
            )
        document = Document(
            blocks=tuple(block for chapter in book.chapters for block in chapter.document.blocks)
        )
        return (_draft(document, self.book_name(book), label, source_format),)


def _draft(document: Document, own_title: str, label: str, source_format: Format) -> SourceDraft:
    return SourceDraft(
        document=document,
        kind=Kind.BOOK,
        source_format=source_format,
        own_title=own_title,
        label=label,
        words=count_words(document.text),
    )


def _book(content: Content) -> BookContent:
    assert isinstance(content, BookContent)
    return content


def _words(count: int) -> str:
    return f"{count:,} words"


def _word_range(counts: list[int]) -> str:
    low, high = min(counts), max(counts)
    return _words(low) if low == high else f"{low:,}–{_words(high)}"
