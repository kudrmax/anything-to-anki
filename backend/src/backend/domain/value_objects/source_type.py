from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    TEXT      = "text"
    LYRICS    = "lyrics"
    SUBTITLES = "subtitles"
