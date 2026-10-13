from __future__ import annotations

import logging
from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.application.constants import BOOK_CHAPTER_TITLE_SETTING
from backend.application.dto.book_dtos import (
    BookChapterPreviewDTO,
    BookSourcesCreated,
    BookSplitRequired,
)
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.chapter_title_template import (
    DEFAULT_CHAPTER_TITLE_TEMPLATE,
    ChapterTitleTemplate,
)
from backend.domain.value_objects.content_type import resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.book_reader import BookReader
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.book import Book

logger = logging.getLogger(__name__)


class CreateBookSourcesUseCase:
    """Turns a book file into text sources.

    One source per chapter, gathered in a collection, or one source for the whole book.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        collection_repo: CollectionRepository,
        settings_repo: SettingsRepository,
        book_reader: BookReader,
    ) -> None:
        self._source_repo = source_repo
        self._collection_repo = collection_repo
        self._settings_repo = settings_repo
        self._book_reader = book_reader

    def execute(
        self,
        path: str,
        title: str | None,
        split: bool | None,
    ) -> BookSplitRequired | BookSourcesCreated:
        """Without a `split` choice, a book of several chapters asks for one first."""
        book = self._book_reader.read(path)
        book_name = (title or "").strip() or book.title or PurePath(path).stem
        if len(book.chapters) == 1:
            split = False
        if split is None:
            return self._split_preview(book, book_name)
        if split:
            return self._create_chapters(book, book_name)
        return self._create_whole(book, book_name)

    def _split_preview(self, book: Book, book_name: str) -> BookSplitRequired:
        template = self._title_template()
        return BookSplitRequired(
            book_name=book_name,
            word_count=book.word_count,
            chapters=[
                BookChapterPreviewDTO(
                    title=template.render(book_name, number, chapter.title),
                    word_count=chapter.word_count,
                )
                for number, chapter in enumerate(book.chapters, start=1)
            ],
        )

    def _create_chapters(self, book: Book, book_name: str) -> BookSourcesCreated:
        template = self._title_template()
        collection_id = self._collection_id(book_name)
        source_ids = [
            self._create_source(
                chapter.text,
                template.render(book_name, number, chapter.title),
                collection_id,
            )
            for number, chapter in enumerate(book.chapters, start=1)
        ]
        logger.info(
            "Created %d chapter sources of book %r in collection id=%s",
            len(source_ids),
            book_name,
            collection_id,
        )
        return BookSourcesCreated(source_ids=source_ids, collection_id=collection_id)

    def _create_whole(self, book: Book, book_name: str) -> BookSourcesCreated:
        source_id = self._create_source(book.text, book_name, None)
        logger.info("Created book source id=%s title=%r", source_id, book_name)
        return BookSourcesCreated(source_ids=[source_id], collection_id=None)

    def _create_source(self, text: str, title: str, collection_id: int | None) -> int:
        source = self._source_repo.create(
            Source(
                raw_text=text,
                status=SourceStatus.NEW,
                input_method=InputMethod.BOOK_FILE,
                content_type=resolve_content_type(InputMethod.BOOK_FILE),
                title=title,
                collection_id=collection_id,
            )
        )
        assert source.id is not None
        return source.id

    def _collection_id(self, name: str) -> int:
        """A book added again joins its existing collection."""
        existing = next((c for c in self._collection_repo.list_all() if c.name == name), None)
        collection = existing or self._collection_repo.create(Collection(name=name))
        assert collection.id is not None
        return collection.id

    def _title_template(self) -> ChapterTitleTemplate:
        pattern = self._settings_repo.get(
            BOOK_CHAPTER_TITLE_SETTING, DEFAULT_CHAPTER_TITLE_TEMPLATE
        )
        return ChapterTitleTemplate(pattern or DEFAULT_CHAPTER_TITLE_TEMPLATE)
