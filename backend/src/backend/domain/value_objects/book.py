from __future__ import annotations

from dataclasses import dataclass

CHAPTER_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class BookChapter:
    title: str | None
    text: str
    word_count: int


@dataclass(frozen=True)
class Book:
    """The readable prose of a book, in reading order."""

    title: str | None
    chapters: tuple[BookChapter, ...]

    @property
    def word_count(self) -> int:
        return sum(chapter.word_count for chapter in self.chapters)

    @property
    def text(self) -> str:
        return CHAPTER_SEPARATOR.join(chapter.text for chapter in self.chapters)
