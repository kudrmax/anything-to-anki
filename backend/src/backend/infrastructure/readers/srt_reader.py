from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import SubtitlesContent
from backend.domain.value_objects.format import Format
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser
from backend.infrastructure.readers.subtitles import subtitles_document
from backend.infrastructure.readers.text_input import input_text, input_title

if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class SrtReader(FormatReader):
    """Subtitles without a video."""

    def __init__(self, file_reader: FileReader) -> None:
        self._file_reader = file_reader
        self._parser = RegexSrtParser()

    @property
    def format(self) -> Format:
        return Format.SRT

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        return ()

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        srt_text = input_text(source_input, self._file_reader)
        return SubtitlesContent(
            title=input_title(source_input),
            document=subtitles_document(srt_text, self._parser),
        )
