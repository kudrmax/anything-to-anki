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

    def reset_to_initial_state(self) -> Source:
        from backend.domain.value_objects.source_status import SourceStatus

        return Source(
            id=self.id,
            raw_text=self.raw_text,
            title=self.title,
            input_method=self.input_method,
            content_type=self.content_type,
            source_url=self.source_url,
            video_path=self.video_path,
            audio_track_index=self.audio_track_index,
            created_at=self.created_at,
            status=SourceStatus.NEW,
        )


_SOURCE_INPUT_FIELDS: frozenset[str] = frozenset({
    "id", "raw_text", "title", "input_method", "content_type",
    "source_url", "video_path", "audio_track_index", "created_at",
})

_SOURCE_DERIVED_FIELDS: frozenset[str] = frozenset({
    "status", "cleaned_text", "error_message", "processing_stage",
})
