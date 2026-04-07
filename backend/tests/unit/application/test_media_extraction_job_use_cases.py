import pytest
from unittest.mock import MagicMock, patch
from backend.application.use_cases.manage_media_extraction import (
    StartMediaExtractionUseCase,
    GetMediaExtractionStatusUseCase,
)
from backend.application.use_cases.run_media_extraction_job import RunMediaExtractionJobUseCase
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.media_extraction_job import MediaExtractionJob
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus


def _make_candidate(id: int, fragment: str = "hello world") -> StoredCandidate:
    return StoredCandidate(
        id=id, source_id=1, lemma="test", pos="NOUN",
        cefr_level="B1", zipf_frequency=3.5, is_sweet_spot=True,
        context_fragment=fragment, fragment_purity="clean", occurrences=1,
        status=CandidateStatus.LEARN,
        media=CandidateMedia(
            candidate_id=id,
            screenshot_path=None,
            audio_path=None,
            start_ms=1000,
            end_ms=2000,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=None,
        ),
    )


@pytest.mark.unit
class TestStartMediaExtractionUseCase:
    def test_creates_job_with_eligible_candidates(self) -> None:
        job_repo = MagicMock()
        media_repo = MagicMock()
        source_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [1, 2]
        created_job = MagicMock()
        created_job.id = 42
        job_repo.create.return_value = created_job

        uc = StartMediaExtractionUseCase(
            job_repo=job_repo,
            media_repo=media_repo,
            source_repo=source_repo,
        )
        result = uc.execute(source_id=1)

        assert result.id == 42
        job_arg = job_repo.create.call_args[0][0]
        assert job_arg.total_candidates == 2
        assert set(job_arg.candidate_ids) == {1, 2}

    def test_skips_candidates_without_timecodes(self) -> None:
        job_repo = MagicMock()
        media_repo = MagicMock()
        source_repo = MagicMock()
        # Only candidate 1 is eligible (2 was filtered out by repo)
        media_repo.get_eligible_candidate_ids.return_value = [1]
        created_job = MagicMock()
        created_job.id = 1
        job_repo.create.return_value = created_job

        uc = StartMediaExtractionUseCase(
            job_repo=job_repo,
            media_repo=media_repo,
            source_repo=source_repo,
        )
        uc.execute(source_id=1)

        job_arg = job_repo.create.call_args[0][0]
        assert job_arg.total_candidates == 1
        assert job_arg.candidate_ids == [1]

    def test_includes_pending_candidates_in_job(self) -> None:
        job_repo = MagicMock()
        media_repo = MagicMock()
        source_repo = MagicMock()
        # Repo handles filtering: returns learn + pending, excludes known
        media_repo.get_eligible_candidate_ids.return_value = [1, 2]
        job_repo.create.side_effect = lambda j: j

        uc = StartMediaExtractionUseCase(
            job_repo=job_repo,
            media_repo=media_repo,
            source_repo=source_repo,
        )

        job = uc.execute(source_id=42)

        assert job.total_candidates == 2
        assert sorted(job.candidate_ids) == [1, 2]  # learn + pending, NOT known


@pytest.mark.unit
class TestRunMediaExtractionJobUseCase:
    def test_extracts_screenshot_and_audio_for_each_candidate(self) -> None:
        job = MediaExtractionJob(
            id=1, source_id=1,
            status=MediaExtractionJobStatus.PENDING,
            total_candidates=1,
            candidate_ids=[10],
        )
        job_repo = MagicMock()
        job_repo.get_by_id.return_value = job
        candidate = _make_candidate(10)
        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = MagicMock(video_path="/tmp/movie.mp4")
        media_extractor = MagicMock()
        media_repo = MagicMock()

        uc = RunMediaExtractionJobUseCase(
            job_repo=job_repo,
            candidate_repo=candidate_repo,
            source_repo=source_repo,
            media_extractor=media_extractor,
            media_root="/tmp/media",
            media_repo=media_repo,
        )

        with patch("backend.application.use_cases.run_media_extraction_job.os.path.exists", return_value=True), \
             patch("backend.application.use_cases.run_media_extraction_job.os.makedirs"):
            uc.execute(job_id=1)

        media_extractor.extract_screenshot.assert_called_once()
        media_extractor.extract_audio.assert_called_once()
        media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = media_repo.upsert.call_args[0][0]
        assert upserted.candidate_id == 10
        assert upserted.screenshot_path == "/tmp/media/1/10_screenshot.webp"
        assert upserted.audio_path == "/tmp/media/1/10_audio.m4a"
        assert upserted.start_ms == 1000
        assert upserted.end_ms == 2000
