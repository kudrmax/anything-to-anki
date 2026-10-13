from __future__ import annotations

from backend.domain.exceptions import BookReadError
from backend.domain.ports.book_reader import BookReader
from backend.domain.value_objects.book import Book, BookChapter
from backend.infrastructure.epub import EpubError, EpubReader


class EpubBookReader(BookReader):
    """Reads epub books through the standalone epub module."""

    def __init__(self) -> None:
        self._reader = EpubReader()

    def read(self, path: str) -> Book:
        try:
            book = self._reader.read(path)
        except EpubError as e:
            raise BookReadError(str(e)) from e
        return Book(
            title=book.title,
            chapters=tuple(
                BookChapter(title=c.title, text=c.text, word_count=c.word_count)
                for c in book.chapters
            ),
        )
