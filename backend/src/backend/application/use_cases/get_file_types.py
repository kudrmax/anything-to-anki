from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import FileTypesDTO
from backend.domain.value_objects.format import Format

if TYPE_CHECKING:
    from backend.domain.ports.format_detector import FormatDetector


class GetFileTypesUseCase:
    """Which files are videos and which are subtitles that can be attached to them."""

    def __init__(self, detector: FormatDetector) -> None:
        self._detector = detector

    def execute(self) -> FileTypesDTO:
        return FileTypesDTO(
            video_extensions=list(self._detector.extensions(Format.VIDEO_FILE)),
            subtitle_extensions=list(self._detector.extensions(Format.SRT)),
        )
