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

    @property
    def shown_job_types(self) -> tuple[JobType, ...]:
        """The jobs a card shows as this kind being made: a follow-up about the meaning
        makes the meaning too."""
        if self is GenerationKind.MEANING:
            return (JobType.MEANING, JobType.MEANING_FOLLOW_UP)
        return (self.job_type,)
