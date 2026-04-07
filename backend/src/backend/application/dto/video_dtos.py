from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.audio_track_info import AudioTrackInfo
    from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


@dataclass(frozen=True)
class VideoSourceCreated:
    """Source was created successfully."""

    source_id: int
    status: str = "created"


@dataclass(frozen=True)
class TrackSelectionRequired:
    """Ambiguous track configuration — user must choose subtitle and/or audio track.

    Either list may be empty: an empty list means that side needs no selection
    (already resolved — 0 or 1 track, or provided externally).
    """

    subtitle_tracks: list[SubtitleTrackInfo] = field(default_factory=list)
    audio_tracks: list[AudioTrackInfo] = field(default_factory=list)
    status: str = "track_selection_required"
