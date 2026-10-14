from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.job_status import JobStatus

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository


@dataclass(frozen=True)
class GenerationCard:
    """A shown phrase of a word: what the ✨ menu works on."""

    word: StoredCandidate
    phrase: Occurrence

    @property
    def word_id(self) -> int:
        assert self.word.id is not None
        return self.word.id

    @property
    def phrase_id(self) -> int:
        assert self.phrase.id is not None
        return self.phrase.id

    @property
    def in_play(self) -> bool:
        """The word is not known and the phrase is not skipped."""
        return self.word.status is not CandidateStatus.KNOWN and not self.phrase.skipped


@dataclass(frozen=True)
class CardJobs:
    """The jobs of cards: of their phrases, and of their words for the kinds of a word."""

    by_phrase: dict[int, dict[str, Job]]
    by_word: dict[int, dict[str, Job]]

    @classmethod
    def of(cls, job_repo: JobRepository, cards: list[GenerationCard]) -> CardJobs:
        return cls(
            by_phrase=job_repo.get_jobs_for_phrases([c.phrase_id for c in cards]),
            by_word=job_repo.get_jobs_for_candidates(sorted({c.word_id for c in cards})),
        )


class GenerationCards:
    """The cards of a source: every shown phrase with its word, words in source order."""

    def __init__(
        self, candidate_repo: CandidateRepository, occurrence_repo: OccurrenceRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo

    def of_source(self, source_id: int) -> list[GenerationCard]:
        shown = self._occurrence_repo.shown_by_word(source_id)
        return [
            GenerationCard(word, phrase)
            for word in self._candidate_repo.get_by_source(source_id)
            if word.id is not None
            for phrase in shown.get(word.id, [])
        ]


class GenerationTarget(ABC):
    """One kind of background generation: which cards get it and when a card has it.

    A kind of a phrase is made for each shown phrase; a kind of a word once per word.
    """

    kind: GenerationKind
    of_word: bool = False

    @abstractmethod
    def applies_to(self, source: Source) -> bool:
        """The source's cards need this kind at all."""

    @abstractmethod
    def is_done(self, card: GenerationCard) -> bool:
        """The card already has the result."""

    def covers(self, card: GenerationCard) -> bool:
        """The card is one this kind is made for: still in play and able to get it."""
        return card.in_play

    def blocker(self, source: Source, video_downloading: bool) -> GenerationBlocker | None:
        """What has to happen before generation can start, if anything."""
        return None

    @abstractmethod
    def discard(self, card: GenerationCard) -> None:
        """Drop the card's result so the worker makes it again."""

    def cards(self, cards: list[GenerationCard]) -> list[GenerationCard]:
        """The cards this kind is made for; a kind of a word takes one card per word."""
        covered = [c for c in cards if self.covers(c)]
        if not self.of_word:
            return covered
        seen: set[int] = set()
        first_of_word: list[GenerationCard] = []
        for card in covered:
            if card.word_id not in seen:
                seen.add(card.word_id)
                first_of_word.append(card)
        return first_of_word

    def job(self, card: GenerationCard) -> Job:
        if self.of_word:
            return Job.queued(self.kind.job_type, card.word.source_id, card.word_id)
        return Job.queued(
            self.kind.job_type, card.word.source_id, card.word_id,
            phrase_id=card.phrase_id, phrase_revision=card.phrase.revision,
        )

    def job_of(self, jobs: CardJobs, card: GenerationCard) -> Job | None:
        by_key = (
            jobs.by_word.get(card.word_id, {}) if self.of_word
            else jobs.by_phrase.get(card.phrase_id, {})
        )
        return by_key.get(self.kind.job_type.value)

    def state(self, card: GenerationCard, job: Job | None) -> CardGenerationState:
        if job is not None and job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            return CardGenerationState.RUNNING
        if self.is_done(card):
            return CardGenerationState.DONE
        if job is not None:
            return CardGenerationState.FAILED
        return CardGenerationState.MISSING


class PolishTarget(GenerationTarget):
    kind = GenerationKind.POLISH

    def __init__(self, occurrence_repo: OccurrenceRepository) -> None:
        self._occurrence_repo = occurrence_repo

    def applies_to(self, source: Source) -> bool:
        return source.can_polish_phrases

    def is_done(self, card: GenerationCard) -> bool:
        return card.phrase.polished_phrase is not None

    def discard(self, card: GenerationCard) -> None:
        self._occurrence_repo.write_text(
            card.phrase_id, card.phrase.source_phrase, card.phrase.phrase_position,
            polished=None,
        )


class MeaningTarget(GenerationTarget):
    kind = GenerationKind.MEANING

    def __init__(self, meaning_repo: CandidateMeaningRepository) -> None:
        self._meaning_repo = meaning_repo

    def applies_to(self, source: Source) -> bool:
        return True

    def is_done(self, card: GenerationCard) -> bool:
        meaning = card.phrase.meaning
        return meaning is not None and meaning.meaning is not None

    def discard(self, card: GenerationCard) -> None:
        self._meaning_repo.delete_by_phrase_id(card.phrase_id)


class InPlaceGenerationTarget(GenerationTarget):
    """A kind whose worker overwrites the result: the old one stays until the new one lands."""

    def discard(self, card: GenerationCard) -> None:
        pass


class MediaTarget(InPlaceGenerationTarget):
    """Screenshot and audio cut from the source video."""

    kind = GenerationKind.MEDIA

    def applies_to(self, source: Source) -> bool:
        return source.has_video

    def covers(self, card: GenerationCard) -> bool:
        media = card.phrase.media
        if media is None or media.start_ms is None or media.end_ms is None:
            return False
        return super().covers(card)

    def is_done(self, card: GenerationCard) -> bool:
        media = card.phrase.media
        return media is not None and media.screenshot_path is not None

    def blocker(self, source: Source, video_downloading: bool) -> GenerationBlocker | None:
        if source.video_path is not None:
            return None
        if video_downloading:
            return GenerationBlocker.VIDEO_DOWNLOADING
        return GenerationBlocker.VIDEO_NOT_DOWNLOADED


class PronunciationTarget(InPlaceGenerationTarget):
    """Dictionary recordings of the target word."""

    kind = GenerationKind.PRONUNCIATION
    of_word = True

    def applies_to(self, source: Source) -> bool:
        return True

    def is_done(self, card: GenerationCard) -> bool:
        return card.word.pronunciation is not None


class TTSTarget(InPlaceGenerationTarget):
    """The card phrase read aloud by a synthetic voice; a video has its own audio."""

    kind = GenerationKind.TTS

    def applies_to(self, source: Source) -> bool:
        return not source.has_video

    def is_done(self, card: GenerationCard) -> bool:
        tts = card.phrase.tts
        return tts is not None and tts.audio_path is not None


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
