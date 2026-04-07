from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    TEXT      = "text"
    LYRICS    = "lyrics"
    SUBTITLES = "subtitles"
    VIDEO     = "video"
