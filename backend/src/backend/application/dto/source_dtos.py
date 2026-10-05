from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.application.dto.cefr_dtos import (
    CEFRBreakdownDTO,  # noqa: TC001 — Pydantic needs this at runtime
)
from backend.application.dto.cloze_dtos import CandidateClozeDTO
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.domain.entities.stored_candidate import StoredCandidate


class CreateSourceRequest(BaseModel):
    """Input for creating a new text source."""

    raw_text: str
    input_method: InputMethod = InputMethod.TEXT_PASTED
    title: str | None = None


class UpdateTitleRequest(BaseModel):
    """Input for renaming a source."""

    title: str


class SourceDTO(BaseModel):
    """Summary view of a source (for list endpoints)."""

    id: int
    title: str
    raw_text_preview: str
    status: str
    source_type: str
    content_type: str
    source_url: str | None = None
    video_downloaded: bool = False
    created_at: datetime
    candidate_count: int
    learn_count: int
    decided_count: int = 0
    processing_stage: str | None = None
    collection_id: int | None = None
    collection_name: str | None = None
    awaiting_generation: bool = False
    generation_status: str | None = None  # 'queued' | 'running' | 'failed'
    generation_error: str | None = None
    # Built-in source: it can't be deleted or reprocessed.
    is_permanent: bool = False


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


class StoredCandidateDTO(BaseModel):
    """A persisted word candidate."""

    id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    # The user has complained about this card at least once.
    reported: bool = False
    # The phrase as it stands in the source.
    context_fragment: str
    # The phrase the card shows: polished by AI unless reverted.
    phrase: str
    # AI's easier version, only when it differs from the source phrase.
    polished_fragment: str | None = None
    polish_reverted: bool = False
    polish_status: str | None = None  # 'queued' | 'running' | 'failed' while AI works on it
    fragment_purity: str
    occurrences: int
    status: str
    surface_form: str | None = None
    is_phrasal_verb: bool = False
    has_custom_context_fragment: bool = False
    meaning: CandidateMeaningDTO | None = None
    media: CandidateMediaDTO | None = None
    pronunciation: CandidatePronunciationDTO | None = None
    tts: CandidateTTSDTO | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None
    frequency_band: str | None = None
    origin: PhraseOriginDTO | None = None
    cloze: CandidateClozeDTO | None = None
    # False once the card is in Anki: its note type can no longer change.
    can_cloze: bool = True


class SourceDetailDTO(BaseModel):
    """Detailed view of a source with candidates."""

    id: int
    title: str
    raw_text: str
    cleaned_text: str | None
    status: str
    source_type: str
    content_type: str
    can_polish_phrases: bool = False
    has_source_text: bool = True
    source_url: str | None = None
    video_downloaded: bool = False
    error_message: str | None
    processing_stage: str | None = None
    created_at: datetime
    candidates: list[StoredCandidateDTO]
    # How many candidates to show before "show more"; None — show all.
    initially_shown_candidates: int | None = None


SourceDetailDTO.model_rebuild()


def _derive_meaning_status(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None,
) -> tuple[str, str | None]:
    """Return (status, error) for the meaning enrichment."""
    if jobs_by_candidate and c.id is not None:
        jobs_for_cand = jobs_by_candidate.get(c.id, {})
        job = jobs_for_cand.get("meaning")
        if job is not None:
            return job.status.value, job.error
    if c.meaning is not None and c.meaning.meaning is not None:
        return "done", None
    return "done", None  # no job and no meaning = just not started, show as done


def _derive_media_status(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None,
) -> tuple[str, str | None]:
    """Return (status, error) for the media enrichment."""
    if jobs_by_candidate and c.id is not None:
        jobs_for_cand = jobs_by_candidate.get(c.id, {})
        job = jobs_for_cand.get("media")
        if job is not None:
            return job.status.value, job.error
    if c.media is not None and c.media.screenshot_path is not None:
        return "done", None
    if c.media is not None and c.media.start_ms is not None:
        return "idle", None
    return "done", None


def _derive_pronunciation_status(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None,
) -> tuple[str, str | None]:
    """Return (status, error) for the pronunciation enrichment."""
    if jobs_by_candidate and c.id is not None:
        jobs_for_cand = jobs_by_candidate.get(c.id, {})
        job = jobs_for_cand.get("pronunciation")
        if job is not None:
            return job.status.value, job.error
    if c.pronunciation is not None and (
        c.pronunciation.us_audio_path is not None
        or c.pronunciation.uk_audio_path is not None
    ):
        return "done", None
    return "done", None


def _derive_tts_status(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None,
) -> tuple[str, str | None]:
    """Return (status, error) for the TTS enrichment."""
    if jobs_by_candidate and c.id is not None:
        jobs_for_cand = jobs_by_candidate.get(c.id, {})
        job = jobs_for_cand.get("tts")
        if job is not None:
            return job.status.value, job.error
    if c.tts is not None and c.tts.audio_path is not None:
        return "done", None
    return "done", None


def _polish_status(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None,
) -> str | None:
    if not jobs_by_candidate or c.id is None:
        return None
    job = jobs_by_candidate.get(c.id, {}).get(JobType.POLISH.value)
    return job.status.value if job is not None else None


def stored_candidate_to_dto(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None = None,
    reported_ids: set[int] | None = None,
    synced_ids: set[int] | None = None,
) -> StoredCandidateDTO:
    """Canonical converter: StoredCandidate entity → StoredCandidateDTO.

    Every use case that needs to serialise a StoredCandidate MUST use this
    function instead of hand-rolling the mapping.

    ``jobs_by_candidate`` maps candidate_id → {job_type_value: Job}.
    When provided, enrichment status/error are derived from jobs.

    ``synced_ids`` are the candidates already in Anki; they can't become cloze cards.
    """
    from backend.application.dto.cefr_dtos import breakdown_to_dto

    meaning_dto: CandidateMeaningDTO | None = None
    if c.meaning is not None:
        m_status, m_error = _derive_meaning_status(c, jobs_by_candidate)
        meaning_dto = CandidateMeaningDTO(
            meaning=c.meaning.meaning,
            translation=c.meaning.translation,
            synonyms=c.meaning.synonyms,
            examples=c.meaning.examples,
            ipa=c.meaning.ipa,
            status=m_status,
            error=m_error,
            generated_at=c.meaning.generated_at,
        )
    else:
        # No meaning row, but maybe there's a queued/running/failed job
        if jobs_by_candidate and c.id is not None:
            jobs_for_cand = jobs_by_candidate.get(c.id, {})
            job = jobs_for_cand.get("meaning")
            if job is not None:
                meaning_dto = CandidateMeaningDTO(
                    meaning=None,
                    translation=None,
                    synonyms=None,
                    examples=None,
                    ipa=None,
                    status=job.status.value,
                    error=job.error,
                    generated_at=None,
                )

    media_dto: CandidateMediaDTO | None = None
    if c.media is not None:
        md_status, md_error = _derive_media_status(c, jobs_by_candidate)
        media_dto = CandidateMediaDTO(
            screenshot_path=c.media.screenshot_path,
            audio_path=c.media.audio_path,
            start_ms=c.media.start_ms,
            end_ms=c.media.end_ms,
            status=md_status,
            error=md_error,
            generated_at=c.media.generated_at,
        )
    else:
        if jobs_by_candidate and c.id is not None:
            jobs_for_cand = jobs_by_candidate.get(c.id, {})
            job = jobs_for_cand.get("media")
            if job is not None:
                media_dto = CandidateMediaDTO(
                    screenshot_path=None,
                    audio_path=None,
                    start_ms=None,
                    end_ms=None,
                    status=job.status.value,
                    error=job.error,
                    generated_at=None,
                )

    pronunciation_dto: CandidatePronunciationDTO | None = None
    if c.pronunciation is not None:
        p_status, p_error = _derive_pronunciation_status(c, jobs_by_candidate)
        pronunciation_dto = CandidatePronunciationDTO(
            us_audio_path=c.pronunciation.us_audio_path,
            uk_audio_path=c.pronunciation.uk_audio_path,
            status=p_status,
            error=p_error,
            generated_at=c.pronunciation.generated_at,
        )
    else:
        if jobs_by_candidate and c.id is not None:
            jobs_for_cand = jobs_by_candidate.get(c.id, {})
            job = jobs_for_cand.get("pronunciation")
            if job is not None:
                pronunciation_dto = CandidatePronunciationDTO(
                    us_audio_path=None,
                    uk_audio_path=None,
                    status=job.status.value,
                    error=job.error,
                    generated_at=None,
                )

    tts_dto: CandidateTTSDTO | None = None
    if c.tts is not None:
        t_status, t_error = _derive_tts_status(c, jobs_by_candidate)
        tts_dto = CandidateTTSDTO(
            audio_path=c.tts.audio_path,
            status=t_status,
            error=t_error,
            generated_at=c.tts.generated_at,
        )
    else:
        if jobs_by_candidate and c.id is not None:
            jobs_for_cand = jobs_by_candidate.get(c.id, {})
            job = jobs_for_cand.get("tts")
            if job is not None:
                tts_dto = CandidateTTSDTO(
                    audio_path=None,
                    status=job.status.value,
                    error=job.error,
                    generated_at=None,
                )

    breakdown_dto: CEFRBreakdownDTO | None = None
    if c.cefr_breakdown is not None:
        breakdown_dto = breakdown_to_dto(c.cefr_breakdown)

    return StoredCandidateDTO(
        id=c.id,  # type: ignore[arg-type]
        lemma=c.lemma,
        pos=c.pos,
        cefr_level=c.cefr_level,
        zipf_frequency=c.zipf_frequency,
        is_sweet_spot=c.is_sweet_spot,
        reported=reported_ids is not None and c.id in reported_ids,
        context_fragment=c.context_fragment,
        phrase=c.card_phrase,
        polished_fragment=c.polished_fragment if c.is_polished else None,
        polish_reverted=c.polish_reverted,
        polish_status=_polish_status(c, jobs_by_candidate),
        fragment_purity=c.fragment_purity,
        occurrences=c.occurrences,
        status=c.status.value,
        surface_form=c.surface_form,
        is_phrasal_verb=c.is_phrasal_verb,
        has_custom_context_fragment=c.has_custom_context_fragment,
        meaning=meaning_dto,
        media=media_dto,
        pronunciation=pronunciation_dto,
        tts=tts_dto,
        cefr_breakdown=breakdown_dto,
        usage_distribution=c.usage_distribution.to_dict() if c.usage_distribution else None,
        frequency_band=c.frequency_band.name,
        origin=(
            PhraseOriginDTO(kind=c.origin.kind.value, source_title=c.origin.source_title)
            if c.origin is not None
            else None
        ),
        cloze=_cloze_dto(c),
        can_cloze=synced_ids is None or c.id not in synced_ids,
    )


def _cloze_dto(c: StoredCandidate) -> CandidateClozeDTO | None:
    cloze = ClozeBuilder().effective(c)
    if cloze is None:
        return None
    return CandidateClozeDTO(
        hidden_word_indices=list(cloze.hidden_word_indices),
        hint_kind=cloze.hint_kind.value,
        custom_hint=cloze.custom_hint,
    )
