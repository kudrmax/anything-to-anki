from __future__ import annotations

from pydantic import BaseModel


class BookChapterPreviewDTO(BaseModel):
    """A source the book would become when split: its title and size."""

    title: str
    word_count: int


class BookSplitRequired(BaseModel):
    """The book has several chapters — the user chooses whether to split it."""

    book_name: str
    word_count: int
    chapters: list[BookChapterPreviewDTO]


class BookSourcesCreated(BaseModel):
    """Sources made from a book; a split book's chapters are gathered in a collection."""

    source_ids: list[int]
    collection_id: int | None
