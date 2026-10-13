from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.source import Source
from backend.domain.value_objects.content import Kind, LocalVideo, YouTubeVideo
from backend.domain.value_objects.content_type import resolve_content_type
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_path_resolver import VideoPathResolver
    from backend.domain.value_objects.content import VideoRef
    from backend.domain.value_objects.document import Document

DEFAULT_TITLE_LENGTH = 100

# input_method and content_type go away together with the pipeline that reads them.
_INPUT_METHOD_BY_FORMAT: dict[Format, InputMethod] = {
    Format.PLAIN: InputMethod.TEXT_PASTED,
    Format.HTML: InputMethod.TEXT_PASTED,
    Format.MARKDOWN: InputMethod.MARKDOWN_FILE,
    Format.EPUB: InputMethod.BOOK_FILE,
    Format.SRT: InputMethod.SUBTITLES_FILE,
    Format.VIDEO_FILE: InputMethod.VIDEO_FILE,
    Format.YOUTUBE: InputMethod.YOUTUBE_URL,
}


class SourceWriter:
    """Stores a new source together with its document."""

    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        video_path_resolver: VideoPathResolver,
    ) -> None:
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._video_path_resolver = video_path_resolver

    def write(
        self,
        *,
        document: Document,
        title: str | None,
        source_format: Format,
        kind: Kind,
        video: VideoRef | None = None,
        collection_id: int | None = None,
        created_at: datetime | None = None,
    ) -> int:
        input_method = (
            InputMethod.LYRICS_PASTED
            if kind is Kind.SONG
            else _INPUT_METHOD_BY_FORMAT[source_format]
        )
        source = Source(
            raw_text=document.text,
            status=SourceStatus.NEW,
            input_method=input_method,
            content_type=resolve_content_type(input_method),
            title=title or document.text[:DEFAULT_TITLE_LENGTH],
            collection_id=collection_id,
            created_at=created_at or datetime.now(tz=UTC),
            format=source_format,
            kind=kind,
        )
        match video:
            case LocalVideo():
                source.video_path = self._video_path_resolver.to_storage_path(
                    video.path, InputMethod.VIDEO_FILE
                )
                source.audio_track_index = video.audio_track
            case YouTubeVideo():
                source.source_url = video.url
        created = self._source_repo.create(source)
        assert created.id is not None
        self._document_repo.save(created.id, document)
        return created.id
