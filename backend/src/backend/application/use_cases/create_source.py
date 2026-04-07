from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.video_dtos import SubtitleSelectionRequired, VideoSourceCreated
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.subtitle_extractor import SubtitleExtractor


class CreateSourceUseCase:
    """Creates a new text source for processing."""

    def __init__(
        self,
        source_repo: SourceRepository,
        subtitle_extractor: SubtitleExtractor | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._subtitle_extractor = subtitle_extractor

    def execute(
        self,
        raw_text: str,
        source_type: SourceType = SourceType.TEXT,
        title: str | None = None,
    ) -> Source:
        if not raw_text.strip():
            msg = "Source text cannot be empty"
            raise ValueError(msg)
        resolved_title = title.strip() if title and title.strip() else raw_text[:100]
        source = Source(
            raw_text=raw_text,
            status=SourceStatus.NEW,
            source_type=source_type,
            title=resolved_title,
        )
        return self._source_repo.create(source)

    def execute_video(
        self,
        video_path: str,
        srt_text: str | None,
        title: str | None,
        track_index: int | None = None,
    ) -> VideoSourceCreated | SubtitleSelectionRequired:
        """Create a VIDEO source. Returns selection request if track ambiguity exists."""
        raw_srt: str

        if srt_text is not None:
            raw_srt = srt_text
        else:
            assert self._subtitle_extractor is not None
            tracks = self._subtitle_extractor.list_tracks(video_path)

            if len(tracks) == 0:
                raise ValueError("No subtitles found in video. Please attach a .srt file.")

            if len(tracks) == 1:
                raw_srt = self._subtitle_extractor.extract(video_path, tracks[0].index)

            elif track_index is not None:
                raw_srt = self._subtitle_extractor.extract(video_path, track_index)

            else:
                return SubtitleSelectionRequired(tracks=tracks)

        resolved_title = (title or "").strip() or video_path.rsplit("/", 1)[-1]
        source = Source(
            raw_text=raw_srt,
            status=SourceStatus.NEW,
            source_type=SourceType.VIDEO,
            title=resolved_title,
            video_path=video_path,
        )
        created = self._source_repo.create(source)
        return VideoSourceCreated(source_id=created.id)  # type: ignore[arg-type]
