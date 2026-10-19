from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.services.card_view import card_view, open_elsewhere, wants_ready_generation
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.review_card import CardContext, ReviewCard

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.section_stamper import SectionStamper
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.value_objects.card_choice import WordState


@dataclass(frozen=True)
class GenerationCard:
    """A shown phrase of a word: what the ✨ menu works on.

    `in_play`: someone decides on the card or sends it to Anki (the card view's
    `wants_generation`).
    """

    word: StoredCandidate
    phrase: Occurrence
    in_play: bool

    @classmethod
    def of(cls, word: StoredCandidate, phrase: Occurrence, context: CardContext) -> GenerationCard:
        assert phrase.id is not None
        elsewhere = open_elsewhere(context.word, context.knowledge)
        view = card_view(context.word, phrase.id, context.knowledge, elsewhere, context.now)
        return cls(word, phrase, view.wants_generation)

    @property
    def word_id(self) -> int:
        assert self.word.id is not None
        return self.word.id

    @property
    def phrase_id(self) -> int:
        assert self.phrase.id is not None
        return self.phrase.id

    @property
    def review_card(self) -> ReviewCard:
        return ReviewCard(word=self.word, occurrence=self.phrase)


@dataclass(frozen=True)
class ReadyCards:
    """The cards that want ready generation, and the words that have one."""

    phrase_ids: frozenset[int]
    word_ids: frozenset[int]

    @classmethod
    def of(cls, cards: list[GenerationCard], sorter: CandidateSorter) -> ReadyCards:
        shown = sorter.open_sections([card.review_card for card in cards])
        ready = [
            card for card in cards
            if wants_ready_generation(card.in_play, shown[card.phrase_id])
        ]
        return cls(
            phrase_ids=frozenset(card.phrase_id for card in ready),
            word_ids=frozenset(card.word_id for card in ready),
        )


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
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._contexts = CardContexts(word_states, vocabulary)

    def of_source(self, source_id: int) -> list[GenerationCard]:
        shown = self._occurrence_repo.shown_by_word(source_id)
        words = [
            word for word in self._candidate_repo.get_by_source(source_id)
            if word.id is not None and word.id in shown
        ]
        contexts = self._contexts.of_source(source_id)
        return [
            GenerationCard.of(word, phrase, contexts[word.id])
            for word in words
            if word.id is not None
            for phrase in shown[word.id]
        ]


class CardContexts:
    """What the card view of each word's cards is read from: the word's cards, what the
    user knows of its lemma, and the request's moment."""

    def __init__(self, word_states: WordStateRepository, vocabulary: UserVocabulary) -> None:
        self._word_states = word_states
        self._vocabulary = vocabulary

    def of_source(self, source_id: int) -> dict[int, CardContext]:
        return {
            word_id: self.of(state)
            for word_id, state in self._word_states.of_source(source_id).items()
        }

    def of_word(self, word_id: int) -> CardContext | None:
        state = self._word_states.of_word(word_id)
        return self.of(state) if state is not None else None

    def of(self, state: WordState) -> CardContext:
        return CardContext(
            word=state, knowledge=self._vocabulary.of(state.lemma),
            now=self._vocabulary.scope.now,
        )


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

    def is_ready(self, ready: ReadyCards, card: GenerationCard) -> bool:
        """The card wants ready generation; a kind of a word asks any card of the word."""
        if self.of_word:
            return card.word_id in ready.word_ids
        return card.phrase_id in ready.phrase_ids

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

    def __init__(self, occurrence_repo: OccurrenceRepository, stamper: SectionStamper) -> None:
        self._occurrence_repo = occurrence_repo
        self._stamper = stamper

    def applies_to(self, source: Source) -> bool:
        return source.can_polish_phrases

    def is_done(self, card: GenerationCard) -> bool:
        return card.phrase.polished_phrase is not None

    def discard(self, card: GenerationCard) -> None:
        self._occurrence_repo.write_text(
            card.phrase_id, card.phrase.source_phrase, card.phrase.phrase_position,
            earned_section=self._stamper.earned(card.phrase.source_phrase, card.word),
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
