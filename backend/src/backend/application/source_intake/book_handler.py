from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.constants import NAMING_RULE_SETTING
from backend.application.dto.add_source_dtos import SourcesCreated
from backend.application.source_intake.kind_handler import KindHandler
from backend.domain.entities.collection import Collection
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.services.word_count import count_words
from backend.domain.value_objects.content import BookContent, Kind
from backend.domain.value_objects.document import Document
from backend.domain.value_objects.naming_rule import DEFAULT_NAMING_RULE, NamingRule
from backend.domain.value_objects.question import (
    DetailItem,
    OptionDetails,
    Question,
    QuestionOption,
)

if TYPE_CHECKING:
    from backend.application.source_intake.source_writer import SourceWriter
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers

logger = logging.getLogger(__name__)

SPLIT_QUESTION_ID = "book.split"
SPLIT_OPTION_ID = "split"
WHOLE_OPTION_ID = "whole"
UNTITLED_BOOK = "Book"


class BookHandler(KindHandler):
    """A book becomes a source per chapter, gathered in a collection named after the book,
    or one source. A book of several chapters asks which, showing the chapters first."""

    def __init__(
        self,
        writer: SourceWriter,
        collection_repo: CollectionRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self._writer = writer
        self._collection_repo = collection_repo
        self._settings_repo = settings_repo

    @property
    def kind(self) -> Kind:
        return Kind.BOOK

    def questions(self, content: Content) -> tuple[Question, ...]:
        book = _book(content)
        if len(book.chapters) < 2:
            return ()
        name = _book_name(book)
        template = self._title_template()
        counts = [count_words(chapter.document.text) for chapter in book.chapters]
        chapters = tuple(
            DetailItem(
                text=template.render(name, number, _own_title(chapter.title, number)),
                note=_words(count),
            )
            for number, (chapter, count) in enumerate(zip(book.chapters, counts, strict=True), 1)
        )
        split = QuestionOption(
            id=SPLIT_OPTION_ID,
            label=f"{len(chapters)} chapters · {_word_range(counts)} each",
            details=OptionDetails(title=f"Sources in collection «{name}»", items=chapters),
        )
        whole = QuestionOption(id=WHOLE_OPTION_ID, label=f"One source · {_words(sum(counts))}")
        return (
            Question(
                id=SPLIT_QUESTION_ID,
                prompt=f"Add «{name}» as",
                options=(split, whole),
                default=SPLIT_OPTION_ID,
            ),
        )

    def create(self, content: Content, answers: Answers, source_format: Format) -> SourcesCreated:
        book = _book(content)
        name = _book_name(book)
        if len(book.chapters) > 1 and answers.get(SPLIT_QUESTION_ID) == SPLIT_OPTION_ID:
            return self._create_chapters(book, name, source_format)
        return self._create_whole(book, name, source_format)

    def _create_chapters(
        self, book: BookContent, name: str, source_format: Format,
    ) -> SourcesCreated:
        template = self._title_template()
        collection_id = self._collection_id(name)
        # Added at one moment, the chapters keep their reading order in the newest-first list.
        added_at = datetime.now(tz=UTC)
        source_ids = [
            self._writer.write(
                document=chapter.document,
                title=template.render(name, number, _own_title(chapter.title, number)),
                source_format=source_format,
                kind=Kind.BOOK,
                collection_id=collection_id,
                created_at=added_at,
            )
            for number, chapter in enumerate(book.chapters, start=1)
        ]
        logger.info(
            "Created %d chapter sources of book %r in collection id=%s",
            len(source_ids), name, collection_id,
        )
        return SourcesCreated(source_ids=source_ids, collection_id=collection_id)

    def _create_whole(self, book: BookContent, name: str, source_format: Format) -> SourcesCreated:
        document = Document(
            blocks=tuple(block for chapter in book.chapters for block in chapter.document.blocks)
        )
        source_id = self._writer.write(
            document=document, title=name, source_format=source_format, kind=Kind.BOOK,
        )
        logger.info("Created book source id=%s title=%r", source_id, name)
        return SourcesCreated(source_ids=[source_id])

    def _collection_id(self, name: str) -> int:
        """A book added again joins its existing top-level collection; a new one goes last."""
        tree = CollectionTree(self._collection_repo.list_all())
        existing = tree.find_top_level(name)
        collection = existing or self._collection_repo.create(
            Collection(name=name.strip(), position=tree.next_position(None)),
        )
        assert collection.id is not None
        return collection.id

    def _title_template(self) -> NamingRule:
        pattern = self._settings_repo.get(
            NAMING_RULE_SETTING, DEFAULT_NAMING_RULE
        )
        return NamingRule(pattern or DEFAULT_NAMING_RULE)


def _own_title(title: str | None, number: int) -> str:
    return title or f"Chapter {number}"


def _book(content: Content) -> BookContent:
    assert isinstance(content, BookContent)
    return content


def _book_name(book: BookContent) -> str:
    return book.title or UNTITLED_BOOK


def _words(count: int) -> str:
    return f"{count:,} words"


def _word_range(counts: list[int]) -> str:
    low, high = min(counts), max(counts)
    return _words(low) if low == high else f"{low:,}–{_words(high)}"
