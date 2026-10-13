from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import DetectedFormatDTO
from backend.application.utils.typed_path import normalize_typed_path
from backend.domain.exceptions import UnsupportedUrlError
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import LocalFile

if TYPE_CHECKING:
    from backend.domain.ports.format_detector import FormatDetector
    from backend.domain.value_objects.source_input import SourceInput

UNSUPPORTED_LINK_LABEL = "Link not supported"
PLAIN_TEXT_EXTENSION = "txt"
_LABELS: dict[Format, str] = {
    Format.PLAIN: "Text",
    Format.MARKDOWN: "Text · markdown",
    Format.HTML: "Text · html",
    Format.EPUB: "Book · epub",
    Format.SRT: "Subtitles · srt",
    Format.VIDEO_FILE: "Video",
    Format.YOUTUBE: "Video · YouTube",
}
# A file's own extension says more than the format's name.
_LABELLED_BY_EXTENSION: frozenset[Format] = frozenset({Format.PLAIN, Format.VIDEO_FILE})


class DetectFormatUseCase:
    """Tells how an input will be read, for the hint under the input field."""

    def __init__(self, detector: FormatDetector) -> None:
        self._detector = detector

    def execute(self, source_input: SourceInput) -> DetectedFormatDTO:
        if isinstance(source_input, LocalFile):
            source_input = LocalFile(path=normalize_typed_path(source_input.path))
        try:
            source_format = self._detector.detect(source_input)
        except UnsupportedUrlError:
            return DetectedFormatDTO(format=None, label=UNSUPPORTED_LINK_LABEL)
        label = _LABELS[source_format]
        if isinstance(source_input, LocalFile) and source_format in _LABELLED_BY_EXTENSION:
            extension = PurePath(source_input.path).suffix.lstrip(".").lower()
            label = f"{label} · {extension or PLAIN_TEXT_EXTENSION}"
        return DetectedFormatDTO(format=source_format, label=label)
