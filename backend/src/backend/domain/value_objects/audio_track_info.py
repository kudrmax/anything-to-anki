from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioTrackInfo:
    """Metadata about one audio track embedded in a video file."""

    index: int
    language: str | None   # e.g. "eng", "rus"
    title: str | None      # e.g. "English 5.1", "Director's commentary"
    codec: str             # e.g. "aac", "ac3"
    channels: int | None   # e.g. 2, 6
