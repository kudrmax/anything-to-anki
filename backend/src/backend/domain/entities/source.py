from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.content_type import ContentType
    from backend.domain.value_objects.input_method import InputMethod
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


EVERYWHERE_SOURCE_TITLE = "From everywhere"


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
    collection_id: int | None = None
    processing_stage: ProcessingStage | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @classmethod
    def everywhere(cls) -> Source:
        """The built-in source of phrases met anywhere and added one by one by hand."""
        from backend.domain.value_objects.content_type import ContentType
        from backend.domain.value_objects.input_method import InputMethod
        from backend.domain.value_objects.source_status import SourceStatus

        return cls(
            raw_text="",
            status=SourceStatus.DONE,
            input_method=InputMethod.PHRASE_ADDED,
            content_type=ContentType.PHRASES,
            title=EVERYWHERE_SOURCE_TITLE,
        )

    @property
    def is_permanent(self) -> bool:
        """The app always keeps it: it can't be deleted, and there is nothing to reprocess."""
        from backend.domain.value_objects.content_type import ContentType

        return self.content_type == ContentType.PHRASES

    @property
    def has_text(self) -> bool:
        """Topics and hand-added phrases have no text of their own to show."""
        from backend.domain.value_objects.content_type import ContentType

        return self.content_type not in (ContentType.TOPIC, ContentType.PHRASES)

    @property
    def searchable_text(self) -> str | None:
        """Plain text other sources may borrow phrases from, if there is any yet.

        Raw subtitles and lyrics carry markup, so they count only once cleaned.
        """
        from backend.domain.value_objects.input_method import InputMethod

        if not self.has_text:
            return None
        if self.cleaned_text:
            return self.cleaned_text
        if self.input_method == InputMethod.TEXT_PASTED:
            return self.raw_text
        return None

    @property
    def can_polish_phrases(self) -> bool:
        """A video card cuts its clip by the source phrase, so its phrase must stay as is.

        A hand-added phrase is kept exactly as the user met it.
        """
        from backend.domain.value_objects.content_type import ContentType

        return self.content_type not in (ContentType.VIDEO, ContentType.PHRASES)

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
            collection_id=self.collection_id,
            created_at=self.created_at,
            status=SourceStatus.NEW,
        )


_SOURCE_INPUT_FIELDS: frozenset[str] = frozenset({
    "id", "raw_text", "title", "input_method", "content_type",
    "source_url", "video_path", "audio_track_index", "collection_id", "created_at",
})

_SOURCE_DERIVED_FIELDS: frozenset[str] = frozenset({
    "status", "cleaned_text", "error_message", "processing_stage",
})
