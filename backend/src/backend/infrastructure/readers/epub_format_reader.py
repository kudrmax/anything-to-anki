from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.domain.exceptions import BookReadError, InvalidSourceInputError
from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import BookContent, Chapter
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import LocalFile
from backend.infrastructure.epub import EpubError, EpubReader
from backend.infrastructure.readers.xhtml_document import xhtml_document

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class EpubFormatReader(FormatReader):
    """An epub book, chapter by chapter."""

    def __init__(self) -> None:
        self._reader = EpubReader()

    @property
    def format(self) -> Format:
        return Format.EPUB

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return ()

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        if not isinstance(source_input, LocalFile):
            msg = "A book is read from a file"
            raise InvalidSourceInputError(msg)
        try:
            book = self._reader.read(source_input.path)
        except EpubError as e:
            raise BookReadError(str(e)) from e
        return BookContent(
            title=book.title or PurePath(source_input.path).stem,
            chapters=tuple(
                Chapter(title=chapter.title, document=xhtml_document(chapter.blocks))
                for chapter in book.chapters
            ),
        )
