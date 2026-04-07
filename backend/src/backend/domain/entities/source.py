from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


@dataclass
class Source:
    """A text source submitted for vocabulary analysis."""

    raw_text: str
    status: SourceStatus
    id: int | None = None
    title: str | None = None
    cleaned_text: str | None = None
    error_message: str | None = None
    source_type: SourceType = SourceType.TEXT
    video_path: str | None = None  # absolute path to video file on disk (VIDEO sources only)
    audio_track_index: int | None = None  # selected audio track index for media extraction (None = ffmpeg default)
    processing_stage: ProcessingStage | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
