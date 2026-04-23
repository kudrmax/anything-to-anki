from __future__ import annotations

from pydantic import BaseModel


class FileSourceRequest(BaseModel):
    """Input for creating a source from a local file path."""

    file_path: str
    srt_path: str | None = None
    title: str | None = None
    subtitle_track_index: int | None = None
    audio_track_index: int | None = None
