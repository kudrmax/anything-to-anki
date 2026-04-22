"""Tests for stored_candidate_to_dto and status derivation functions."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.application.dto.source_dtos import stored_candidate_to_dto
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.job import Job
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _make_candidate(
    *,
    cid: int = 1,
    meaning: CandidateMeaning | None = None,
    media: CandidateMedia | None = None,
    pronunciation: CandidatePronunciation | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=10,
        lemma="test",
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="a test",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
        meaning=meaning,
        media=media,
        pronunciation=pronunciation,
    )


def _make_job(
    *,
    job_type: JobType,
    status: JobStatus = JobStatus.QUEUED,
    error: str | None = None,
    candidate_id: int = 1,
    job_id: int = 100,
) -> Job:
    return Job(
        id=job_id,
        job_type=job_type,
        candidate_id=candidate_id,
        source_id=10,
        status=status,
        error=error,
        created_at=NOW,
        started_at=None,
    )


def _jobs_dict(jobs: list[Job]) -> dict[int, dict[str, Job]]:
    result: dict[int, dict[str, Job]] = {}
    for j in jobs:
        cid = j.candidate_id
        if cid is not None:
            result.setdefault(cid, {})[j.job_type.value] = j
    return result


@pytest.mark.unit
class TestStoredCandidateToDtoStatusDerivation:
    """Test all branches of status derivation in stored_candidate_to_dto."""

    # --- No jobs, no enrichment data ---

    def test_no_jobs_no_enrichment_data(self) -> None:
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=None)
        assert dto.meaning is None
        assert dto.media is None
        assert dto.pronunciation is None

    # --- No jobs, enrichment data exists ---

    def test_no_jobs_meaning_data_exists(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(meaning=meaning)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=None)
        assert dto.meaning is not None
        assert dto.meaning.status == "done"
        assert dto.meaning.error is None

    def test_no_jobs_media_with_screenshot(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path="/img.png", audio_path=None,
            start_ms=None, end_ms=None, generated_at=NOW,
        )
        c = _make_candidate(media=media)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=None)
        assert dto.media is not None
        assert dto.media.status == "done"

    def test_no_jobs_media_with_timecodes_no_screenshot(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=1000, end_ms=5000, generated_at=None,
        )
        c = _make_candidate(media=media)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=None)
        assert dto.media is not None
        assert dto.media.status == "idle"

    def test_no_jobs_pronunciation_with_audio(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1, us_audio_path="/us.mp3", uk_audio_path=None,
            generated_at=NOW,
        )
        c = _make_candidate(pronunciation=pron)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=None)
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "done"

    # --- Jobs exist, no enrichment data ---

    def test_meaning_job_queued_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.QUEUED)
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "queued"
        assert dto.meaning.meaning is None

    def test_meaning_job_running_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.RUNNING)
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "running"

    def test_meaning_job_failed_with_error_no_data(self) -> None:
        job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.FAILED,
            error="AI service unavailable",
        )
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "failed"
        assert dto.meaning.error == "AI service unavailable"

    def test_media_job_queued_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEDIA, status=JobStatus.QUEUED)
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.media is not None
        assert dto.media.status == "queued"
        assert dto.media.screenshot_path is None

    def test_pronunciation_job_running_no_data(self) -> None:
        job = _make_job(job_type=JobType.PRONUNCIATION, status=JobStatus.RUNNING)
        c = _make_candidate()
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "running"

    # --- Jobs exist, enrichment data also exists (job overrides) ---

    def test_meaning_job_overrides_data_status(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.RUNNING)
        c = _make_candidate(meaning=meaning)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.meaning is not None
        # Job status overrides "done" from existing data
        assert dto.meaning.status == "running"

    def test_media_job_overrides_data_status(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path="/img.png", audio_path=None,
            start_ms=None, end_ms=None, generated_at=NOW,
        )
        job = _make_job(job_type=JobType.MEDIA, status=JobStatus.FAILED, error="timeout")
        c = _make_candidate(media=media)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.media is not None
        assert dto.media.status == "failed"
        assert dto.media.error == "timeout"

    def test_pronunciation_job_overrides_data_status(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1, us_audio_path="/us.mp3", uk_audio_path=None,
            generated_at=NOW,
        )
        job = _make_job(job_type=JobType.PRONUNCIATION, status=JobStatus.QUEUED)
        c = _make_candidate(pronunciation=pron)
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "queued"

    # --- Multiple job types for same candidate ---

    def test_multiple_job_types_each_gets_own_status(self) -> None:
        meaning_job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.RUNNING, job_id=100,
        )
        media_job = _make_job(
            job_type=JobType.MEDIA, status=JobStatus.QUEUED, job_id=101,
        )
        pron_job = _make_job(
            job_type=JobType.PRONUNCIATION, status=JobStatus.FAILED,
            error="not found", job_id=102,
        )
        c = _make_candidate()
        dto = stored_candidate_to_dto(
            c, jobs_by_candidate=_jobs_dict([meaning_job, media_job, pron_job]),
        )
        assert dto.meaning is not None
        assert dto.meaning.status == "running"
        assert dto.media is not None
        assert dto.media.status == "queued"
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "failed"
        assert dto.pronunciation.error == "not found"

    # --- Empty jobs dict (no jobs for this candidate) ---

    def test_empty_jobs_dict_with_data(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(meaning=meaning)
        dto = stored_candidate_to_dto(c, jobs_by_candidate={})
        assert dto.meaning is not None
        assert dto.meaning.status == "done"

    def test_jobs_for_different_candidate_ignored(self) -> None:
        """Jobs for a different candidate_id don't affect this candidate's DTO."""
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(cid=1, meaning=meaning)
        # Job belongs to candidate_id=999, not 1
        job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.RUNNING, candidate_id=999,
        )
        dto = stored_candidate_to_dto(c, jobs_by_candidate=_jobs_dict([job]))
        # No matching job for candidate 1 → status from data
        assert dto.meaning is not None
        assert dto.meaning.status == "done"
