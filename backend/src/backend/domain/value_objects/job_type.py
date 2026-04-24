from __future__ import annotations

from enum import Enum


class JobType(Enum):
    MEANING = "meaning"
    MEDIA = "media"
    PRONUNCIATION = "pronunciation"
    VIDEO_DOWNLOAD = "video_download"
    TTS = "tts"
