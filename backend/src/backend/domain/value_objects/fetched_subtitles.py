from __future__ import annotations

from dataclasses import dataclass

from backend.domain.value_objects.input_method import InputMethod


@dataclass(frozen=True)
class FetchedSubtitles:
    """Result of fetching subtitles from a URL source."""

    srt_text: str
    title: str
    input_method: InputMethod
