from __future__ import annotations

from enum import StrEnum


class GenerationBlocker(StrEnum):
    """Why a kind of generation can't start right now."""

    VIDEO_NOT_DOWNLOADED = "video_not_downloaded"
    VIDEO_DOWNLOADING = "video_downloading"
