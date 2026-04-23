from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.video_dtos import TrackSelectionRequired, VideoSourceCreated
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType, resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.audio_track_lister import AudioTrackLister
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.subtitle_extractor import SubtitleExtractor
    from backend.domain.ports.video_path_resolver import VideoPathResolver
    from backend.domain.value_objects.audio_track_info import AudioTrackInfo
    from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo

logger = logging.getLogger(__name__)


class CreateSourceUseCase:
    """Creates a new text source for processing."""

    _VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".mov"})

    def __init__(
        self,
        source_repo: SourceRepository,
        subtitle_extractor: SubtitleExtractor | None = None,
        audio_track_lister: AudioTrackLister | None = None,
        file_reader: FileReader | None = None,
        video_path_resolver: VideoPathResolver | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._subtitle_extractor = subtitle_extractor
        self._audio_track_lister = audio_track_lister
        self._file_reader = file_reader
        self._video_path_resolver = video_path_resolver

    def execute(
        self,
        raw_text: str,
        input_method: InputMethod = InputMethod.TEXT_PASTED,
        title: str | None = None,
    ) -> Source:
        if not raw_text.strip():
            msg = "Source text cannot be empty"
            raise ValueError(msg)
        resolved_title = title.strip() if title and title.strip() else raw_text[:100]
        source = Source(
            raw_text=raw_text,
            status=SourceStatus.NEW,
            input_method=input_method,
            content_type=resolve_content_type(input_method),
            title=resolved_title,
        )
        return self._source_repo.create(source)

    def execute_video(
        self,
        video_path: str,
        srt_text: str | None,
        title: str | None,
        subtitle_track_index: int | None = None,
        audio_track_index: int | None = None,
    ) -> VideoSourceCreated | TrackSelectionRequired:
        """Create a VIDEO source. Returns selection request if track ambiguity exists."""
        # --- 1. Resolve subtitles ---
        raw_srt: str | None = None
        pending_subtitle_tracks: list[SubtitleTrackInfo] = []

        if srt_text is not None:
            if not srt_text.strip():
                raise ValueError("Attached .srt file is empty.")
            raw_srt = srt_text
        else:
            assert self._subtitle_extractor is not None
            sub_tracks = self._subtitle_extractor.list_tracks(video_path)
            logger.info(
                "Video %s: found %d subtitle track(s)",
                video_path, len(sub_tracks),
            )

            if len(sub_tracks) == 0:
                raise ValueError("No subtitles found in video. Please attach a .srt file.")

            if len(sub_tracks) == 1:
                raw_srt = self._subtitle_extractor.extract(video_path, sub_tracks[0].index)
            elif subtitle_track_index is not None:
                raw_srt = self._subtitle_extractor.extract(video_path, subtitle_track_index)
            else:
                pending_subtitle_tracks = sub_tracks

        # --- 2. Resolve audio track ---
        resolved_audio_index: int | None = audio_track_index
        pending_audio_tracks: list[AudioTrackInfo] = []

        if self._audio_track_lister is not None:
            audio_tracks = self._audio_track_lister.list_audio_tracks(video_path)
            logger.info(
                "Video %s: found %d audio track(s)",
                video_path, len(audio_tracks),
            )

            if len(audio_tracks) <= 1:
                # 0 or 1 audio tracks — ffmpeg default is fine, keep as None
                resolved_audio_index = None
            elif audio_track_index is not None:
                resolved_audio_index = audio_track_index
            else:
                pending_audio_tracks = audio_tracks

        # --- 3. If anything is pending, return selection request ---
        if pending_subtitle_tracks or pending_audio_tracks:
            return TrackSelectionRequired(
                subtitle_tracks=pending_subtitle_tracks,
                audio_tracks=pending_audio_tracks,
            )

        # --- 4. All resolved — create the source ---
        assert raw_srt is not None
        resolved_title = (title or "").strip() or video_path.rsplit("/", 1)[-1]
        storage_path = (
            self._video_path_resolver.to_storage_path(video_path, InputMethod.VIDEO_FILE)
            if self._video_path_resolver is not None
            else video_path
        )
        source = Source(
            raw_text=raw_srt,
            status=SourceStatus.NEW,
            input_method=InputMethod.VIDEO_FILE,
            content_type=ContentType.VIDEO,
            title=resolved_title,
            video_path=storage_path,
            audio_track_index=resolved_audio_index,
        )
        created = self._source_repo.create(source)
        logger.info(
            "Created video source id=%s title=%r audio_track_index=%s",
            created.id, resolved_title, resolved_audio_index,
        )
        return VideoSourceCreated(source_id=created.id)  # type: ignore[arg-type]

    def execute_from_file(
        self,
        file_path: str,
        srt_path: str | None = None,
        title: str | None = None,
        subtitle_track_index: int | None = None,
        audio_track_index: int | None = None,
    ) -> Source | VideoSourceCreated | TrackSelectionRequired:
        """Create source from a local file path. Determines type by extension."""
        assert self._file_reader is not None
        if not self._file_reader.exists(file_path):
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

        if f".{ext}" in self._VIDEO_EXTENSIONS:
            srt_text: str | None = None
            if srt_path is not None:
                srt_text = self._file_reader.read_text(srt_path)
            return self.execute_video(
                video_path=file_path,
                srt_text=srt_text,
                title=title,
                subtitle_track_index=subtitle_track_index,
                audio_track_index=audio_track_index,
            )

        # Text file — read content, determine input method
        content = self._file_reader.read_text(file_path)
        input_method = InputMethod.SUBTITLES_FILE if ext == "srt" else InputMethod.TEXT_PASTED
        return self.execute(raw_text=content, input_method=input_method, title=title)
