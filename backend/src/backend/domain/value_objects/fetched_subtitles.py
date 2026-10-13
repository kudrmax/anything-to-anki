from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedSubtitles:
    """Result of fetching subtitles from a URL source."""

    srt_text: str
    title: str
