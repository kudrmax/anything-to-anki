from __future__ import annotations

from enum import Enum


class JobType(Enum):
    MEANING = "meaning"
    MEDIA = "media"
    PRONUNCIATION = "pronunciation"
    VIDEO_DOWNLOAD = "video_download"
    TTS = "tts"
    TOPIC_TARGETS = "topic_targets"
    POLISH = "polish"
    MEANING_FOLLOW_UP = "meaning_follow_up"


# The jobs that make something for one phrase; the others work on a word or a source.
PHRASE_JOB_TYPES = frozenset({
    JobType.POLISH, JobType.MEANING, JobType.MEANING_FOLLOW_UP, JobType.MEDIA, JobType.TTS,
})
