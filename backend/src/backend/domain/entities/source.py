from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod

if TYPE_CHECKING:
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


@dataclass
class Source:
    """A text source submitted for vocabulary analysis."""

    raw_text: str
    status: SourceStatus
    input_method: InputMethod
    content_type: ContentType
    id: int | None = None
    title: str | None = None
    cleaned_text: str | None = None
    error_message: str | None = None
    source_url: str | None = None
    video_path: str | None = None
    audio_track_index: int | None = None
    processing_stage: ProcessingStage | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
