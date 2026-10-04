from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository

_ACTIVE_STATUSES = frozenset({CandidateStatus.PENDING, CandidateStatus.LEARN})


class GenerationTarget(ABC):
    """One kind of background generation: which cards get it and when a card has it."""

    kind: GenerationKind

    @abstractmethod
    def applies_to(self, source: Source) -> bool:
        """The source's cards need this kind at all."""

    @abstractmethod
    def is_done(self, candidate: StoredCandidate) -> bool:
        """The card already has the result."""

    def covers(self, candidate: StoredCandidate) -> bool:
        """The card is one this kind is made for: still in play and able to get it."""
        return candidate.status in _ACTIVE_STATUSES

    def blocker(self, source: Source, video_downloading: bool) -> GenerationBlocker | None:
        """What has to happen before generation can start, if anything."""
        return None

    @abstractmethod
    def discard(self, candidate_id: int) -> None:
        """Drop the card's result so the worker makes it again."""

    def state(self, candidate: StoredCandidate, job: Job | None) -> CardGenerationState:
        if job is not None and job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            return CardGenerationState.RUNNING
        if self.is_done(candidate):
            return CardGenerationState.DONE
        if job is not None:
            return CardGenerationState.FAILED
        return CardGenerationState.MISSING


class PolishTarget(GenerationTarget):
    kind = GenerationKind.POLISH

    def __init__(self, candidate_repo: CandidateRepository) -> None:
        self._candidate_repo = candidate_repo

    def applies_to(self, source: Source) -> bool:
        return source.can_polish_phrases

    def is_done(self, candidate: StoredCandidate) -> bool:
        return candidate.polished_fragment is not None

    def discard(self, candidate_id: int) -> None:
        self._candidate_repo.set_polished_fragment(candidate_id, None)


class MeaningTarget(GenerationTarget):
    kind = GenerationKind.MEANING

    def __init__(self, meaning_repo: CandidateMeaningRepository) -> None:
        self._meaning_repo = meaning_repo

    def applies_to(self, source: Source) -> bool:
        return True

    def is_done(self, candidate: StoredCandidate) -> bool:
        return candidate.meaning is not None and candidate.meaning.meaning is not None

    def discard(self, candidate_id: int) -> None:
        self._meaning_repo.delete_by_candidate_id(candidate_id)


class InPlaceGenerationTarget(GenerationTarget):
    """A kind whose worker overwrites the result: the old one stays until the new one lands."""

    def discard(self, candidate_id: int) -> None:
        pass


class MediaTarget(InPlaceGenerationTarget):
    """Screenshot and audio cut from the source video."""

    kind = GenerationKind.MEDIA

    def applies_to(self, source: Source) -> bool:
        return source.content_type == ContentType.VIDEO

    def covers(self, candidate: StoredCandidate) -> bool:
        media = candidate.media
        if media is None or media.start_ms is None or media.end_ms is None:
            return False
        return super().covers(candidate)

    def is_done(self, candidate: StoredCandidate) -> bool:
        return candidate.media is not None and candidate.media.screenshot_path is not None

    def blocker(self, source: Source, video_downloading: bool) -> GenerationBlocker | None:
        if source.video_path is not None:
            return None
        if video_downloading:
            return GenerationBlocker.VIDEO_DOWNLOADING
        return GenerationBlocker.VIDEO_NOT_DOWNLOADED


class PronunciationTarget(InPlaceGenerationTarget):
    """Dictionary recordings of the target word."""

    kind = GenerationKind.PRONUNCIATION

    def applies_to(self, source: Source) -> bool:
        return True

    def is_done(self, candidate: StoredCandidate) -> bool:
        return candidate.pronunciation is not None


class TTSTarget(InPlaceGenerationTarget):
    """The card phrase read aloud by a synthetic voice; a video has its own audio."""

    kind = GenerationKind.TTS

    def applies_to(self, source: Source) -> bool:
        return source.content_type != ContentType.VIDEO

    def is_done(self, candidate: StoredCandidate) -> bool:
        return candidate.tts is not None and candidate.tts.audio_path is not None


def target_for(
    targets: list[GenerationTarget], kind: GenerationKind, source: Source,
) -> GenerationTarget:
    """The target of `kind`, if the source needs that kind at all."""
    from backend.domain.exceptions import GenerationNotSupportedError

    for target in targets:
        if target.kind == kind and target.applies_to(source):
            return target
    assert source.id is not None
    raise GenerationNotSupportedError(source.id, kind.value)


def job_of(
    jobs: dict[int, dict[str, Job]], candidate: StoredCandidate, kind: GenerationKind,
) -> Job | None:
    """The card's job of `kind` from a `JobRepository.get_jobs_for_candidates` mapping."""
    if candidate.id is None:
        return None
    return jobs.get(candidate.id, {}).get(kind.job_type.value)
