from __future__ import annotations

from dataclasses import dataclass

from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


@dataclass(frozen=True)
class VideoSourceCreated:
    """Source was created successfully."""

    source_id: int
    status: str = "created"


@dataclass(frozen=True)
class SubtitleSelectionRequired:
    """Multiple subtitle tracks found — user must choose."""

    tracks: list[SubtitleTrackInfo]
    status: str = "subtitle_selection_required"
