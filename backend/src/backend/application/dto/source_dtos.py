from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.application.dto.cefr_dtos import (
    CEFRBreakdownDTO,  # noqa: TC001 — Pydantic needs this at runtime
)
from backend.application.dto.cloze_dtos import CandidateClozeDTO
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.domain.services.card_decision import (  # Pydantic needs the enums at runtime
    DecisionAction,
    DecisionButton,
    card_state,
)
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.elsewhere import Elsewhere  # noqa: TC001 — Pydantic needs it
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.job import Job
    from backend.domain.services.card_decision import CardState
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.review_card import ReviewCard

DONE = "done"
IDLE = "idle"


class ProgressDTO(BaseModel):
    """Decided cards among the Ready ones: the same numbers on a source, its review and a
    collection."""

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
    # How the source is brought up to date: 'rebuild' | 'refresh', or nothing to offer.
    available_operation: SourceOperationKind | None = None
    # The operation the source is busy with; no other one may start meanwhile.
    busy_with: SourceOperationKind | None = None
    # Why no operation is offered while the source is busy.
    operation_hint: str | None = None
    can_review: bool = False
    can_export: bool = False
    can_delete: bool = False
    # How far the review has got, 0..1; a reviewed source is complete.
    review_fraction: float = 0.0


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
    """A decision button of a card: `action` is what a press sends to the decision of the
    phrase (null — the button is off); `pressed` — it holds the card's decision."""

    button: DecisionButton
    action: DecisionAction | None
    pressed: bool


class CardStateDTO(BaseModel):
    """What a card shows of the decision on its word, and what each button does.

    `decided_elsewhere`: the decision of the word, made on another of its cards.
    `elsewhere`: the word, open here, is known or learned via another source.
    `buttons`: Learn, Cloze, Known, Skip, in this order."""

    decided_here: bool
    decided_elsewhere: WordStatus | None = None
    elsewhere: Elsewhere | None = None
    buttons: list[ButtonDTO] = []

    @staticmethod
    def of(state: CardState) -> CardStateDTO:
        return CardStateDTO(
            decided_here=state.decided_here,
            decided_elsewhere=state.decided_elsewhere,
            elsewhere=state.elsewhere,
            buttons=[
                ButtonDTO(button=b.button, action=b.action, pressed=b.pressed)
                for b in state.buttons
            ],
        )


class CardDTO(BaseModel):
    """A card of the review list: one shown phrase of a word."""

    phrase_id: int
    word_id: int
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
    # ready | extra | probably_known; None when the card was not arranged with its source
    section: str | None = None
    occurrences: int
    # The decision the card shows: pending | learn | known | skip; the word's beats a Skip.
    status: str
    word_status: str  # pending | learn | known
    phrase_skipped: bool = False
    # This card's phrase is the one of the word's decision, the one that goes to Anki.
    is_decision: bool = False
    decision_kind: str | None = None  # learn | cloze, on the decision card
    state: CardStateDTO
    # Done: the word is decided, the phrase skipped, or the word is done via another source.
    is_done: bool = False
    is_phrasal_verb: bool = False
    meaning: CandidateMeaningDTO | None = None
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
    # False once the phrase is in Anki: its note type can no longer change.
    can_cloze: bool = True
    # Where the source phrase stands in the source's document; none for an example
    phrase_position: DocumentPositionDTO | None = None


class SourceDetailDTO(BaseModel):
    """Detailed view of a source with candidates."""

    id: int
    title: str
    status: str
    kind: str | None
    role: str
    has_video: bool = False
    can_polish_phrases: bool = False
    has_source_text: bool = True
    source_url: str | None = None
    video_downloaded: bool = False
    error_message: str | None
    processing_stage: str | None = None
    busy_with: SourceOperationKind | None = None
    learn_count: int = 0  # words to learn
    created_at: datetime
    candidates: list[CardDTO]
    progress: ProgressDTO = ProgressDTO()
    # How many candidates to show before "show more"; None — show all.
    initially_shown_candidates: int | None = None


SourceDetailDTO.model_rebuild()


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
    phrase_id, word_id = card.phrase_id, card.word_id
    polished = occ.polished_phrase
    return CardDTO(
        phrase_id=phrase_id,
        word_id=word_id,
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
        status=card.shown_status.value,
        word_status=card.word_status.value,
        phrase_skipped=occ.skipped,
        is_decision=occ.is_decision,
        decision_kind=occ.decision_kind.value if occ.decision_kind is not None else None,
        state=CardStateDTO.of(card_state(occ, word, card.elsewhere)),
        is_done=card.is_done,
        is_phrasal_verb=word.is_phrasal_verb,
        meaning=_meaning_dto(occ.meaning, jobs.of_phrase(phrase_id, JobType.MEANING)),
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
        can_cloze=not occ.exported,
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
    """A cloze card is the Learn decision card with markup; markup anywhere else is moot."""
    occ = card.occurrence
    if card.word_status is not WordStatus.LEARN or not occ.is_decision:
        return None
    cloze = ClozeBuilder().effective_for(occ.phrase, occ.cloze)
    if cloze is None:
        return None
    return CandidateClozeDTO(
        hidden_word_indices=list(cloze.hidden_word_indices),
        hint_kind=cloze.hint_kind.value,
        custom_hint=cloze.custom_hint,
    )
