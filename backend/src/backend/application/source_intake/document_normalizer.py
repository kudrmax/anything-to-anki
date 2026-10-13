from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.content import BookContent, Chapter
from backend.domain.value_objects.document import (
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
)

if TYPE_CHECKING:
    from backend.domain.ports.text_cleaner import TextCleaner
    from backend.domain.ports.text_normalizer import TextNormalizer
    from backend.domain.value_objects.content import Content

EMPTY_SOURCE_MESSAGE = "Source text cannot be empty"


class DocumentNormalizer:
    """Cleans every line of what was read and spells slang out (wanna → want to).

    Lines left with nothing to read (`[Chorus]`, `♪`) are dropped, and blocks left without lines.
    """

    def __init__(self, cleaner: TextCleaner, normalizer: TextNormalizer) -> None:
        self._cleaner = cleaner
        self._normalizer = normalizer

    def normalize(self, content: Content) -> Content:
        if isinstance(content, BookContent):
            chapters = tuple(
                Chapter(title=chapter.title, document=document)
                for chapter in content.chapters
                if (document := self._document(chapter.document)).blocks
            )
            if not chapters:
                raise InvalidSourceInputError(EMPTY_SOURCE_MESSAGE)
            return replace(content, chapters=chapters)
        document = self._document(content.document)
        if not document.blocks:
            raise InvalidSourceInputError(EMPTY_SOURCE_MESSAGE)
        return replace(content, document=document)

    def _document(self, document: Document) -> Document:
        blocks = (self._block(block) for block in document.blocks)
        return Document(blocks=tuple(block for block in blocks if block is not None))

    def _block(self, block: Block) -> Block | None:
        match block:
            case Heading():
                text = self._text(block.text)
                return replace(block, text=text) if text else None
            case Paragraph() | ListItem():
                lines = self._lines(block.lines)
                return replace(block, lines=lines) if lines else None

    def _lines(self, lines: tuple[Line, ...]) -> tuple[Line, ...]:
        cleaned = (replace(line, text=self._text(line.text)) for line in lines)
        return tuple(line for line in cleaned if line.text)

    def _text(self, text: str) -> str:
        return self._normalizer.normalize(self._cleaner.clean(text)).strip()
