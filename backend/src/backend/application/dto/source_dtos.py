from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.application.dto.cefr_dtos import (
    CEFRBreakdownDTO,  # noqa: TC001 — Pydantic needs this at runtime
)
from backend.domain.value_objects.input_method import InputMethod

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
    processing_stage: str | None = None


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


class StoredCandidateDTO(BaseModel):
    """A persisted word candidate."""

    id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    fragment_purity: str
    occurrences: int
    status: str
    surface_form: str | None = None
    is_phrasal_verb: bool = False
    has_custom_context_fragment: bool = False
    meaning: CandidateMeaningDTO | None = None
    media: CandidateMediaDTO | None = None
    pronunciation: CandidatePronunciationDTO | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None
    frequency_band: str | None = None


class SourceDetailDTO(BaseModel):
    """Detailed view of a source with candidates."""

    id: int
    title: str
    raw_text: str
    cleaned_text: str | None
    status: str
    source_type: str
    content_type: str
    source_url: str | None = None
    video_downloaded: bool = False
    error_message: str | None
    processing_stage: str | None = None
    created_at: datetime
    candidates: list[StoredCandidateDTO]


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


def stored_candidate_to_dto(
    c: StoredCandidate,
    jobs_by_candidate: dict[int, dict[str, Job]] | None = None,
) -> StoredCandidateDTO:
    """Canonical converter: StoredCandidate entity → StoredCandidateDTO.

    Every use case that needs to serialise a StoredCandidate MUST use this
    function instead of hand-rolling the mapping.

    ``jobs_by_candidate`` maps candidate_id → {job_type_value: Job}.
    When provided, enrichment status/error are derived from jobs.
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
        context_fragment=c.context_fragment,
        fragment_purity=c.fragment_purity,
        occurrences=c.occurrences,
        status=c.status.value,
        surface_form=c.surface_form,
        is_phrasal_verb=c.is_phrasal_verb,
        has_custom_context_fragment=c.has_custom_context_fragment,
        meaning=meaning_dto,
        media=media_dto,
        pronunciation=pronunciation_dto,
        cefr_breakdown=breakdown_dto,
        usage_distribution=c.usage_distribution.to_dict() if c.usage_distribution else None,
        frequency_band=c.frequency_band.name,
    )
