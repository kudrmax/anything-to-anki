from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import SongContent, TextContent
from backend.domain.value_objects.format import Format
from backend.infrastructure.epub.xhtml_text import XhtmlTextExtractor
from backend.infrastructure.readers.text_input import (
    TEXT_KIND_QUESTION,
    input_text,
    input_title,
    is_song,
)
from backend.infrastructure.readers.xhtml_document import xhtml_document

if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class HtmlReader(FormatReader):
    """An html page or fragment: its headings, list items and paragraphs."""

    def __init__(self, file_reader: FileReader) -> None:
        self._file_reader = file_reader
        self._extractor = XhtmlTextExtractor()

    @property
    def format(self) -> Format:
        return Format.HTML

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return (TEXT_KIND_QUESTION,)

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        markup = input_text(source_input, self._file_reader)
        blocks = self._extractor.extract(markup).blocks
        title = input_title(source_input)
        if is_song(answers):
            return SongContent(title=title, document=xhtml_document(blocks, song=True))
        return TextContent(title=title, document=xhtml_document(blocks))
