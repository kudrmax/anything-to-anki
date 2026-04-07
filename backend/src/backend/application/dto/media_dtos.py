from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class SourceMediaStats:
    """Media storage footprint for one source."""

    source_id: int
    source_title: str
    screenshot_bytes: int
    audio_bytes: int
    screenshot_count: int
    audio_count: int


class CleanupMediaKind(str, Enum):
    ALL = "all"
    IMAGES = "images"
    AUDIO = "audio"
