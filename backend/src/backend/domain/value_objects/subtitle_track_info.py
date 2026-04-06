from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleTrackInfo:
    """Metadata about one subtitle track embedded in a video file."""

    index: int
    language: str | None   # e.g. "eng", "rus"
    title: str | None      # e.g. "English (SDH)"
    codec: str             # e.g. "subrip", "ass"
