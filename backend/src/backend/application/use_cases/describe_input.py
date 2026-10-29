from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import InputDescriptionDTO
from backend.application.source_intake.typed_input import typed_inputs
from backend.application.utils.typed_path import normalize_typed_path
from backend.domain.exceptions import UnsupportedUrlError
from backend.domain.services.input_language import is_english
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.input_kind import InputKind
from backend.domain.value_objects.input_problem import InputProblem
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url

if TYPE_CHECKING:
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.ports.format_detector import FormatDetector
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.input_kind_classifier import InputKindClassifier

# A single line longer than this is a pasted text, not a phrase or a topic, and never goes
# to spaCy, which would otherwise parse a whole book pasted as one line on every keystroke.
MAX_PHRASE_CHARS = 300
LINE_BREAK = "\n"
PLAIN_TEXT_EXTENSION = "txt"

UNSUPPORTED_LINK_MESSAGE = "This link can't be read"
UNSUPPORTED_LINK_HINT = "Supported: YouTube. For an article, paste its text or save it as a file."
FILE_NOT_FOUND_MESSAGE = "No file at this path"
FILE_NOT_FOUND_HINT = "Check the path or choose the file again."

_LABELS: dict[Format, str] = {
    Format.PLAIN: "Text",
    Format.MARKDOWN: "Text",
    Format.HTML: "Text",
    Format.EPUB: "Book",
    Format.SRT: "Subtitles",
    Format.VIDEO_FILE: "Video",
    Format.YOUTUBE: "Video",
}
_FILE_FORMATS: dict[Format, str] = {
    Format.MARKDOWN: "markdown",
    Format.HTML: "html",
    Format.EPUB: "epub",
    Format.SRT: "srt",
    Format.YOUTUBE: "YouTube",
}
# A file's own extension says more than the format's name.
_LABELLED_BY_EXTENSION: frozenset[Format] = frozenset({Format.PLAIN, Format.VIDEO_FILE})


class DescribeInputUseCase:
    """What the Add screen input becomes: a source, a topic or a phrase — or why it can't be added.

    Cheap checks go first; spaCy parses only one short English line.
    """

    def __init__(
        self,
        detector: FormatDetector,
        file_reader: FileReader,
        text_analyzer: TextAnalyzer,
        classifier: InputKindClassifier,
    ) -> None:
        self._detector = detector
        self._file_reader = file_reader
        self._text_analyzer = text_analyzer
        self._classifier = classifier

    def execute(self, text: str) -> InputDescriptionDTO:
        if not text.strip():
            return InputDescriptionDTO()
        inputs = typed_inputs(text)
        if len(inputs) > 1:
            return self._describe_files([i for i in inputs if isinstance(i, LocalFile)])
        source_input = inputs[0]
        if isinstance(source_input, Url):
            return self._describe_link(source_input)
        if isinstance(source_input, LocalFile):
            return self._describe_file(source_input)
        return self._describe_text(source_input)

    def _describe_link(self, link: Url) -> InputDescriptionDTO:
        try:
            return self._source(self._detector.detect(link))
        except UnsupportedUrlError:
            return InputDescriptionDTO(
                problem=InputProblem.UNSUPPORTED_LINK,
                problem_message=UNSUPPORTED_LINK_MESSAGE,
                problem_hint=UNSUPPORTED_LINK_HINT,
            )

    def _describe_file(self, file: LocalFile) -> InputDescriptionDTO:
        path = normalize_typed_path(file.path)
        if not self._file_reader.exists(path):
            return InputDescriptionDTO(
                problem=InputProblem.FILE_NOT_FOUND,
                problem_message=FILE_NOT_FOUND_MESSAGE,
                problem_hint=FILE_NOT_FOUND_HINT,
            )
        source_format = self._detector.detect(LocalFile(path=path))
        file_format = _FILE_FORMATS.get(source_format)
        if source_format in _LABELLED_BY_EXTENSION:
            file_format = PurePath(path).suffix.lstrip(".").lower() or PLAIN_TEXT_EXTENSION
        return InputDescriptionDTO(
            kind=InputKind.SOURCE,
            format=source_format,
            label=_LABELS[source_format],
            file_format=file_format,
        )

    def _describe_files(self, files: list[LocalFile]) -> InputDescriptionDTO:
        for file in files:
            path = normalize_typed_path(file.path)
            if not self._file_reader.exists(path):
                return InputDescriptionDTO(
                    problem=InputProblem.FILE_NOT_FOUND,
                    problem_message=f"{FILE_NOT_FOUND_MESSAGE}: {PurePath(path).name}",
                    problem_hint=FILE_NOT_FOUND_HINT,
                )
        return InputDescriptionDTO(
            kind=InputKind.SOURCE, label=f"{len(files)} files", several=True,
        )

    def _describe_text(self, pasted: PastedText) -> InputDescriptionDTO:
        line = pasted.text.strip()
        if LINE_BREAK in line or len(line) > MAX_PHRASE_CHARS:
            return self._source(self._detector.detect(pasted))
        if not is_english(line):
            return InputDescriptionDTO(kind=InputKind.TOPIC)
        tokens = self._text_analyzer.analyze(line)
        if len({token.sent_index for token in tokens}) > 1:
            return self._source(self._detector.detect(pasted))
        return InputDescriptionDTO(kind=self._classifier.classify(tokens))

    @staticmethod
    def _source(source_format: Format) -> InputDescriptionDTO:
        return InputDescriptionDTO(
            kind=InputKind.SOURCE,
            format=source_format,
            label=_LABELS[source_format],
            file_format=_FILE_FORMATS.get(source_format),
        )
