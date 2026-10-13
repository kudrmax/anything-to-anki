"""What the readers of text formats share: the input's text, title and the text-or-song choice."""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.question import Answers, Question, QuestionOption
from backend.domain.value_objects.source_input import LocalFile, PastedText

if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.value_objects.source_input import SourceInput

TEXT_KIND_QUESTION_ID = "text.kind"
TEXT_OPTION_ID = "text"
SONG_OPTION_ID = "song"
TEXT_KIND_QUESTION = Question(
    id=TEXT_KIND_QUESTION_ID,
    prompt="Is it a text or a song?",
    options=(QuestionOption(TEXT_OPTION_ID, "Text"), QuestionOption(SONG_OPTION_ID, "Song")),
    default=TEXT_OPTION_ID,
)


def is_song(answers: Answers) -> bool:
    return answers.get(TEXT_KIND_QUESTION_ID) == SONG_OPTION_ID


def input_text(source_input: SourceInput, file_reader: FileReader) -> str:
    match source_input:
        case PastedText():
            return source_input.text
        case LocalFile():
            return file_reader.read_text(source_input.path)
    msg = "This reader takes pasted text or a file"
    raise InvalidSourceInputError(msg)


def input_title(source_input: SourceInput) -> str | None:
    """A file is named after itself; pasted text has no name of its own."""
    if isinstance(source_input, LocalFile):
        return PurePath(source_input.path).stem
    return None


def song_document(lines: list[str]) -> Document:
    """Every line of a song is a line of the document; blank lines part the stanzas."""
    stanzas: list[list[Line]] = [[]]
    for line in lines:
        if line.strip():
            stanzas[-1].append(Line(line.strip()))
        elif stanzas[-1]:
            stanzas.append([])
    return Document(
        blocks=tuple(
            Paragraph(lines=tuple(stanza), mode=ParagraphMode.LINES)
            for stanza in stanzas
            if stanza
        )
    )
