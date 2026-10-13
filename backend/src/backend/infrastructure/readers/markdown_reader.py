from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import SongContent, TextContent
from backend.domain.value_objects.document import (
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.format import Format
from backend.infrastructure.adapters.markdown_blocks import (
    MarkdownBlock,
    MarkdownBlockKind,
    MarkdownBlockParser,
)
from backend.infrastructure.readers.text_input import (
    TEXT_KIND_QUESTION,
    input_text,
    input_title,
    is_song,
    song_document,
)

if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class MarkdownReader(FormatReader):
    """Markdown: headings, list items and paragraphs, with the markup dropped.

    A song keeps its lines as they are: a line starting with `-`, `1.` or `#` is a line too.
    """

    def __init__(self, file_reader: FileReader) -> None:
        self._file_reader = file_reader
        self._parser = MarkdownBlockParser()

    @property
    def format(self) -> Format:
        return Format.MARKDOWN

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return (TEXT_KIND_QUESTION,)

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        text = input_text(source_input, self._file_reader)
        title = input_title(source_input)
        if is_song(answers):
            lines = [self._parser.inline(line) for line in text.splitlines()]
            return SongContent(title=title, document=song_document(lines))
        blocks = tuple(_block(block) for block in self._parser.parse(text))
        return TextContent(title=title, document=Document(blocks=blocks))


def _block(block: MarkdownBlock) -> Block:
    match block.kind:
        case MarkdownBlockKind.HEADING:
            return Heading(level=block.heading_level, text=block.text)
        case MarkdownBlockKind.LIST_ITEM:
            return ListItem(lines=(Line(block.text),), ordered=block.ordered, depth=block.depth)
        case MarkdownBlockKind.PARAGRAPH:
            return Paragraph(lines=(Line(block.text),), mode=ParagraphMode.FLOW)
