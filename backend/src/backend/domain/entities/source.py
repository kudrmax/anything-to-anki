from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.value_objects.source_role import SourceRole

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Kind
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


SAVED_PHRASES_TITLE = "Saved phrases"


@dataclass
class Source:
    """Something the user added to learn from: content with a document, a topic,
    or the saved phrases."""

    status: SourceStatus
    id: int | None = None
    title: str | None = None
    error_message: str | None = None
    source_url: str | None = None
    video_path: str | None = None
    audio_track_index: int | None = None
    collection_id: int | None = None
    processing_stage: ProcessingStage | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    format: Format | None = None
    kind: Kind | None = None
    role: SourceRole = SourceRole.CONTENT
    topic_query: str | None = None

    @classmethod
    def saved_phrases(cls) -> Source:
        """The built-in source of phrases met anywhere and added one by one by hand."""
        from backend.domain.value_objects.source_status import SourceStatus

        return cls(
            status=SourceStatus.DONE,
            title=SAVED_PHRASES_TITLE,
            role=SourceRole.SAVED_PHRASES,
        )

    @property
    def is_permanent(self) -> bool:
        """The app always keeps it: it can't be deleted, and there is nothing to reprocess."""
        return self.role is SourceRole.SAVED_PHRASES

    @property
    def has_text(self) -> bool:
        """Topics and hand-added phrases have no text of their own to show."""
        return self.role is SourceRole.CONTENT

    @property
    def has_video(self) -> bool:
        """Subtitles of a video file or of YouTube. A YouTube video is a video from the start,
        though its file is downloaded only later, on request."""
        from backend.domain.value_objects.format import Format

        return self.format in (Format.VIDEO_FILE, Format.YOUTUBE)

    @property
    def can_polish_phrases(self) -> bool:
        """A video card cuts its clip by the source phrase, so its phrase must stay as is.

        A hand-added phrase is kept exactly as the user met it.
        """
        return not self.has_video and self.role is not SourceRole.SAVED_PHRASES
