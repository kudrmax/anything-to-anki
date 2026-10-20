from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.application.dto.cefr_dtos import (
    CEFRBreakdownDTO,  # noqa: TC001 — Pydantic needs this at runtime
)
from backend.application.dto.cloze_dtos import CandidateClozeDTO
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.domain.services.card_view import Command, ShownTone, Where  # noqa: TC001 — Pydantic
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.services.meaning_action import (  # Pydantic needs it at runtime
    MeaningAction,
    meaning_action,
)
from backend.domain.value_objects.card_choice import (  # Pydantic needs the enums at runtime
    CardChoice,
    Press,
    Refusal,
    is_cloze,
)
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.job import Job
    from backend.domain.entities.source import Source
    from backend.domain.services.card_view import ButtonState, CardView, Shown
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.review_card import ReviewCard

DONE = "done"
IDLE = "idle"


class ProgressDTO(BaseModel):
    """Reviewed cards among Reviewed and open Ready ones: the same numbers on a source, its
    review and a collection."""

    decided: int = 0
    total: int = 0

    @staticmethod
    def of(progress: DecisionProgress) -> ProgressDTO:
        return ProgressDTO(decided=progress.decided, total=progress.total)


class UpdateTitleRequest(BaseModel):
    """Input for renaming a source."""

    title: str


class SourceDTO(BaseModel):
    """Summary view of a source (for list endpoints)."""

    id: int
    title: str
    # The outcome of the source, or 'processing' while it is being processed.
    status: str
    stage: str  # 'in_progress' | 'preparing' | 'ready' | 'reviewed'
    kind: str | None  # 'text' | 'book' | 'subtitles' | 'song'; none for a topic or saved phrases
    role: str  # 'content' | 'topic' | 'saved_phrases'
    has_video: bool = False
    source_url: str | None = None
    video_downloaded: bool = False
    created_at: datetime
    candidate_count: int  # cards: shown phrases
    learn_count: int  # words to learn
    progress: ProgressDTO = ProgressDTO()
    processing_stage: str | None = None
    collection_id: int | None = None
    collection_path: list[str] = []  # e.g. ["Friends", "Season 1"]; empty in Unsorted
    awaiting_generation: bool = False
    generation_status: str | None = None  # 'queued' | 'running' | 'failed'
    generation_error: str | None = None
    # Built-in source: it can't be deleted.
    is_permanent: bool = False
    # How the source is brought up to date, in menu order: 'refresh', 'rebuild'.
    available_operations: list[SourceOperationKind] = []
    # False while another operation holds the source: the offered ones can't start.
    can_start_operation: bool = True
    # The operation the source is busy with; no other one may start meanwhile.
    busy_with: SourceOperationKind | None = None
    # Why the offered operation can't start while the source is busy.
    operation_hint: str | None = None
    can_review: bool = False
    can_export: bool = False
    can_delete: bool = False
    # How far the review has got, 0..1; a reviewed source is complete.
    review_fraction: float = 0.0
    # The line under the progress: what the source is busy with, or where its review is.
    progress_caption: str = ""


class SourceGroupDTO(BaseModel):
    stage: str
    sources: list[SourceDTO]


class SourceBoardDTO(BaseModel):
    """Sources of one scope, grouped by what to do with them next."""

    title: str
    groups: list[SourceGroupDTO]


class PhraseOriginDTO(BaseModel):
    """Where a borrowed or generated phrase came from."""

    kind: str  # 'source' | 'generated'
    source_title: str | None = None


class CandidateMeaningDTO(BaseModel):
    """Meaning enrichment of a candidate (1:1)."""

    meaning: str | None
    translation: str | None
    synonyms: str | None
    examples: str | None
    ipa: str | None
    status: str  # 'queued' | 'running' | 'done' | 'failed'
    error: str | None
    generated_at: datetime | None


class CandidateMediaDTO(BaseModel):
    """Media enrichment of a candidate (1:1)."""

    screenshot_path: str | None
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    status: str
    error: str | None
    generated_at: datetime | None


class CandidatePronunciationDTO(BaseModel):
    """Pronunciation audio enrichment of a candidate (1:1)."""

    us_audio_path: str | None
    uk_audio_path: str | None
    status: str
    error: str | None
    generated_at: datetime | None


class CandidateTTSDTO(BaseModel):
    """TTS audio enrichment of a candidate (1:1)."""

    audio_path: str | None = None
    status: str = "done"
    error: str | None = None
    generated_at: datetime | None = None


class PhraseDTO(BaseModel):
    """A card phrase: text, words by characters [start, end), the target by word numbers."""

    text: str
    words: list[tuple[int, int]]
    target: list[int]

    @staticmethod
    def of(phrase: Phrase) -> PhraseDTO:
        return PhraseDTO(
            text=phrase.text,
            words=[(word.start, word.end) for word in phrase.words],
            target=list(phrase.target),
        )


class ButtonDTO(BaseModel):
    """A decision button of a card. `command`: what a press does — `decide` sends the
    button, `edit_cloze` opens the markup editor, whose Save is the press; null — the
    button is off, and `refused` tells why. `pressed`: the button holds the card's decision."""

    button: Press
    command: Command | None
    pressed: bool
    refused: Refusal | None

    @staticmethod
    def of(button: ButtonState) -> ButtonDTO:
        return ButtonDTO(
            button=button.button, command=button.command, pressed=button.pressed,
            refused=button.refused,
        )


class ShownStatus(StrEnum):
    """The status a card shows, as the API names it."""

    NEW = "new"
    LEARN = "learn"
    LEARNING = "learning"
    KNOWN = "known"


_SHOWN_STATUS: Mapping[WordStatus, ShownStatus] = MappingProxyType(
    {status: ShownStatus[status.name] for status in WordStatus},
)


class ShownDTO(BaseModel):
    """What a card shows of its word: the status, whether the phrase is skipped, and where
    the status comes from: here, another card of the word, another source, or nowhere."""

    status: ShownStatus
    skipped: bool
    where: Where
    # How the card reads at a glance; the decision beats Skip.
    tone: ShownTone

    @staticmethod
    def of(shown: Shown) -> ShownDTO:
        return ShownDTO(
            status=_SHOWN_STATUS[shown.status], skipped=shown.skipped, where=shown.where,
            tone=shown.tone,
        )


class CardStateDTO(BaseModel):
    """What each button does: Learn, Cloze, Known, Skip, in this order."""

    buttons: list[ButtonDTO] = []

    @staticmethod
    def of(view: CardView) -> CardStateDTO:
        return CardStateDTO(buttons=[ButtonDTO.of(b) for b in view.buttons])


class CardSourceDTO(BaseModel):
    """The source a card belongs to, with what its media, video player and actions need."""

    id: int
    has_video: bool
    can_polish_phrases: bool
    # The operation holding the card's source; the card waits while it runs.
    busy_with: SourceOperationKind | None = None

    @classmethod
    def of(cls, source: Source, busy_with: SourceOperationKind | None) -> CardSourceDTO:
        assert source.id is not None
        return cls(
            id=source.id,
            has_video=source.has_video,
            can_polish_phrases=source.can_polish_phrases,
            busy_with=busy_with,
        )


class CardDTO(BaseModel):
    """A card of the review list: one shown phrase of a word."""

    phrase_id: int
    word_id: int
    source: CardSourceDTO
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    # The user has complained about this card at least once.
    reported: bool = False
    # The phrase the card shows: polished by AI or by hand unless reverted.
    phrase: PhraseDTO
    # The phrase as it stands in the source.
    source_phrase: PhraseDTO
    # The rewritten phrase (AI or by hand), only when it differs from the source one.
    polished_phrase: PhraseDTO | None = None
    polish_reverted: bool = False
    polish_status: str | None = None  # 'queued' | 'running' | 'failed' while AI works on it
    # ready | extra | probably_known | reviewed (a done card); None when not arranged
    section: str | None = None
    occurrences: int
    # The user's choice on this card.
    choice: CardChoice
    shown: ShownDTO
    state: CardStateDTO
    # Done: the word is decided, the phrase skipped, or the word is done via another source.
    is_done: bool = False
    is_phrasal_verb: bool = False
    meaning: CandidateMeaningDTO | None = None
    # What to offer on a card without a meaning text: 'generate' | 'retry'; none otherwise.
    meaning_action: MeaningAction | None = None
    media: CandidateMediaDTO | None = None
    meaning_image_path: str | None = None
    pronunciation: CandidatePronunciationDTO | None = None
    tts: CandidateTTSDTO | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None
    frequency_band: str | None = None
    # Where a collected phrase was found: another source, or AI made it.
    origin: PhraseOriginDTO | None = None
    cloze: CandidateClozeDTO | None = None
    # The hidden words of the cloze can change: a cloze not in Anki yet.
    can_edit_cloze: bool = False
    # Where the source phrase stands in the source's document; none for an example
    phrase_position: DocumentPositionDTO | None = None


class ReviewDTO(BaseModel):
    """The review screen of a set of sources: one source, a collection or all of them."""

    # The set's token, as the scope query parameter takes it back.
    scope: str
    title: str
    status: str
    progress: ProgressDTO = ProgressDTO()
    learn_count: int = 0  # words to learn
    candidates: list[CardDTO]
    # How many candidates to show before "show more"; None — show all.
    initially_shown_candidates: int | None = None
    # Some source of the set is held by an operation: its cards wait for it.
    busy: bool = False


ReviewDTO.model_rebuild()


@dataclass(frozen=True)
class CardJobs:
    """Jobs to show on cards: of phrases by phrase id, of words by word id."""

    of_phrases: dict[int, dict[str, Job]] = field(default_factory=dict)
    of_words: dict[int, dict[str, Job]] = field(default_factory=dict)

    def of_phrase(self, phrase_id: int, job_type: JobType) -> Job | None:
        return self.of_phrases.get(phrase_id, {}).get(job_type.value)

    def of_word(self, word_id: int, job_type: JobType) -> Job | None:
        return self.of_words.get(word_id, {}).get(job_type.value)


def card_to_dto(
    card: ReviewCard,
    source: CardSourceDTO,
    jobs: CardJobs | None = None,
    *,
    reported: bool = False,
    section: CandidateSection | None = None,
) -> CardDTO:
    """Canonical converter: a card → CardDTO. Every use case answering with a card uses it.

    Results and jobs of the phrase go with the card; the pronunciation, picture and facts
    are the word's.
    """
    from backend.application.dto.cefr_dtos import breakdown_to_dto

    jobs = jobs or CardJobs()
    word, occ = card.word, card.occurrence
    view = card.view
    phrase_id, word_id = card.phrase_id, card.word_id
    polished = occ.polished_phrase
    meaning_job = jobs.of_phrase(phrase_id, JobType.MEANING)
    return CardDTO(
        phrase_id=phrase_id,
        word_id=word_id,
        source=source,
        lemma=word.lemma,
        pos=word.pos,
        cefr_level=word.cefr_level,
        zipf_frequency=word.zipf_frequency,
        is_sweet_spot=word.is_sweet_spot,
        reported=reported,
        phrase=PhraseDTO.of(occ.phrase),
        source_phrase=PhraseDTO.of(occ.source_phrase),
        polished_phrase=(
            PhraseDTO.of(polished)
            if polished is not None and polished.text != occ.source_phrase.text
            else None
        ),
        polish_reverted=occ.polish_reverted,
        polish_status=_status_of(jobs.of_phrase(phrase_id, JobType.POLISH)),
        section=section.value if section is not None else None,
        occurrences=word.occurrences,
        choice=occ.choice,
        shown=ShownDTO.of(view.shown),
        state=CardStateDTO.of(view),
        is_done=view.is_done,
        is_phrasal_verb=word.is_phrasal_verb,
        meaning=_meaning_dto(occ.meaning, meaning_job),
        meaning_action=meaning_action(
            occ.meaning, meaning_job.status if meaning_job is not None else None,
        ),
        media=_media_dto(occ.media, jobs.of_phrase(phrase_id, JobType.MEDIA)),
        meaning_image_path=word.meaning_image.image_path if word.meaning_image else None,
        pronunciation=_pronunciation_dto(
            word.pronunciation, jobs.of_word(word_id, JobType.PRONUNCIATION),
        ),
        tts=_tts_dto(occ.tts, jobs.of_phrase(phrase_id, JobType.TTS)),
        cefr_breakdown=(
            breakdown_to_dto(word.cefr_breakdown) if word.cefr_breakdown is not None else None
        ),
        usage_distribution=(
            word.usage_distribution.to_dict() if word.usage_distribution else None
        ),
        frequency_band=word.frequency_band.name,
        origin=(
            PhraseOriginDTO(
                kind=occ.collected_from.kind.value,
                source_title=occ.collected_from.source_title,
            )
            if occ.collected_from is not None
            else None
        ),
        cloze=_cloze_dto(card),
        can_edit_cloze=view.can_edit_cloze,
        phrase_position=(
            DocumentPositionDTO.from_position(occ.phrase_position)
            if occ.phrase_position
            else None
        ),
    )


def _status_of(job: Job | None) -> str | None:
    return job.status.value if job is not None else None


def _meaning_dto(meaning: CandidateMeaning | None, job: Job | None) -> CandidateMeaningDTO | None:
    """An active or failed job tells the status; without one, what there is is done."""
    if meaning is None and job is None:
        return None
    return CandidateMeaningDTO(
        meaning=meaning.meaning if meaning else None,
        translation=meaning.translation if meaning else None,
        synonyms=meaning.synonyms if meaning else None,
        examples=meaning.examples if meaning else None,
        ipa=meaning.ipa if meaning else None,
        status=job.status.value if job is not None else DONE,
        error=job.error if job is not None else None,
        generated_at=meaning.generated_at if meaning else None,
    )


def _media_dto(media: CandidateMedia | None, job: Job | None) -> CandidateMediaDTO | None:
    """Timecodes without a picture yet: the clip can be cut, nobody asked for it."""
    if media is None and job is None:
        return None
    if job is not None:
        status = job.status.value
    elif media is not None and media.screenshot_path is None and media.start_ms is not None:
        status = IDLE
    else:
        status = DONE
    return CandidateMediaDTO(
        screenshot_path=media.screenshot_path if media else None,
        audio_path=media.audio_path if media else None,
        start_ms=media.start_ms if media else None,
        end_ms=media.end_ms if media else None,
        status=status,
        error=job.error if job is not None else None,
        generated_at=media.generated_at if media else None,
    )


def _pronunciation_dto(
    pronunciation: CandidatePronunciation | None, job: Job | None,
) -> CandidatePronunciationDTO | None:
    if pronunciation is None and job is None:
        return None
    return CandidatePronunciationDTO(
        us_audio_path=pronunciation.us_audio_path if pronunciation else None,
        uk_audio_path=pronunciation.uk_audio_path if pronunciation else None,
        status=job.status.value if job is not None else DONE,
        error=job.error if job is not None else None,
        generated_at=pronunciation.generated_at if pronunciation else None,
    )


def _tts_dto(tts: CandidateTTS | None, job: Job | None) -> CandidateTTSDTO | None:
    if tts is None and job is None:
        return None
    return CandidateTTSDTO(
        audio_path=tts.audio_path if tts else None,
        status=job.status.value if job is not None else DONE,
        error=job.error if job is not None else None,
        generated_at=tts.generated_at if tts else None,
    )


def _cloze_dto(card: ReviewCard) -> CandidateClozeDTO | None:
    """The markup of a cloze card, in Anki or not; markup kept on a card that is no cloze
    now is moot."""
    occ = card.occurrence
    if not is_cloze(occ.card_state):
        return None
    cloze = ClozeBuilder().effective_for(occ.phrase, occ.cloze)
    if cloze is None:
        return None
    return CandidateClozeDTO(
        hidden_word_indices=list(cloze.hidden_word_indices),
        hint_kind=cloze.hint_kind.value,
        custom_hint=cloze.custom_hint,
    )
