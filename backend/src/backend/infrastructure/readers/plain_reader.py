from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import SongContent, TextContent
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.format import Format
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


class PlainReader(FormatReader):
    """Text without markup: paragraphs apart by blank lines."""

    def __init__(self, file_reader: FileReader) -> None:
        self._file_reader = file_reader

    @property
    def format(self) -> Format:
        return Format.PLAIN

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return (TEXT_KIND_QUESTION,)

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        lines = input_text(source_input, self._file_reader).splitlines()
        title = input_title(source_input)
        if is_song(answers):
            return SongContent(title=title, document=song_document(lines))
        return TextContent(title=title, document=prose_document(lines))


def prose_document(lines: list[str]) -> Document:
    paragraphs: list[list[Line]] = [[]]
    for line in lines:
        if line.strip():
            paragraphs[-1].append(Line(line.strip()))
        elif paragraphs[-1]:
            paragraphs.append([])
    return Document(
        blocks=tuple(
            Paragraph(lines=tuple(paragraph), mode=ParagraphMode.FLOW)
            for paragraph in paragraphs
            if paragraph
        )
    )
