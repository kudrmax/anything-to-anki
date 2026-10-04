from __future__ import annotations

from enum import StrEnum

from backend.domain.value_objects.job_type import JobType


class GenerationKind(StrEnum):
    """Something the background queue makes for every card of a source."""

    POLISH = "polish"
    MEANING = "meaning"
    MEDIA = "media"
    PRONUNCIATION = "pronunciation"
    TTS = "tts"

    @property
    def job_type(self) -> JobType:
        return JobType(self.value)
