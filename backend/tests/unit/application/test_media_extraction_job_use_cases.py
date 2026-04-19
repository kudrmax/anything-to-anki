from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.run_media_extraction_job import MediaExtractionUseCase
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    BadVideoFormatError,
    InvalidTimecodesError,
    PermanentMediaError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_candidate(
    cid: int,
    fragment: str = "hello world",
    start_ms: int | None = 1000,
    end_ms: int | None = 2000,
    media: CandidateMedia | None = None,
) -> StoredCandidate:
    if media is None and start_ms is not None:
        media = CandidateMedia(
            candidate_id=cid,
            screenshot_path=None,
            audio_path=None,
            start_ms=start_ms,
            end_ms=end_ms,
            status=EnrichmentStatus.QUEUED,
            error=None,
            generated_at=None,
        )
    return StoredCandidate(
        id=cid, source_id=1, lemma="test", pos="NOUN",
        cefr_level="B1", zipf_frequency=3.5,
        context_fragment=fragment, fragment_purity="clean", occurrences=1,
        status=CandidateStatus.LEARN,
        media=media,
    )


def _make_source(video_path: str | None = "/tmp/movie.mp4") -> MagicMock:
    source = MagicMock()
    source.id = 1
    source.video_path = video_path
    source.audio_track_index = 0
    return source


@pytest.mark.unit
class TestMediaExtractionUseCase:
    def _make_uc(
        self,
        candidate: StoredCandidate | None = None,
        source: MagicMock | None = None,
    ) -> tuple[MediaExtractionUseCase, MagicMock, MagicMock, MagicMock, MagicMock]:
        candidate_repo = MagicMock()
        media_repo = MagicMock()
        source_repo = MagicMock()
        media_extractor = MagicMock()

        candidate_repo.get_by_id.return_value = candidate
        source_repo.get_by_id.return_value = source

        uc = MediaExtractionUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            source_repo=source_repo,
            media_extractor=media_extractor,
            media_root="/tmp/media",
        )
        return uc, candidate_repo, media_repo, source_repo, media_extractor

    def test_execute_one_success(self) -> None:
        candidate = _make_candidate(10)
        source = _make_source("/tmp/movie.mp4")

        uc, _, media_repo, _, media_extractor = self._make_uc(candidate, source)
        # Pre-upsert guard expects status=RUNNING (set by worker wrapper)
        media_repo.get_by_candidate_id.return_value = CandidateMedia(
            candidate_id=10,
            screenshot_path=None,
            audio_path=None,
            start_ms=1000,
            end_ms=2000,
            status=EnrichmentStatus.RUNNING,
            error=None,
            generated_at=None,
        )

        base = "backend.application.use_cases.run_media_extraction_job.os"
        with (
            patch(f"{base}.path.exists", return_value=True),
            patch(f"{base}.makedirs"),
        ):
            uc.execute_one(10)

        # mark_running is now called by the worker wrapper, not the use case
        media_extractor.extract_screenshot.assert_called_once_with(
            "/tmp/movie.mp4", 1500, "/tmp/media/1/10_screenshot.webp"
        )
        media_extractor.extract_audio.assert_called_once_with(
            "/tmp/movie.mp4", 1000, 2000, "/tmp/media/1/10_audio.m4a",
            audio_track_index=0,
        )

        media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = media_repo.upsert.call_args[0][0]
        assert upserted.candidate_id == 10
        assert upserted.status == EnrichmentStatus.DONE
        assert upserted.screenshot_path == "/tmp/media/1/10_screenshot.webp"
        assert upserted.audio_path == "/tmp/media/1/10_audio.m4a"
        assert upserted.start_ms == 1000
        assert upserted.end_ms == 2000

    def test_execute_one_raises_permanent_when_candidate_missing(self) -> None:
        uc, _, _, _, _ = self._make_uc(candidate=None, source=None)

        with pytest.raises(PermanentMediaError):
            uc.execute_one(99)

    def test_execute_one_raises_invalid_timecodes(self) -> None:
        # Pass start_ms=None so _make_candidate doesn't auto-create media
        candidate = _make_candidate(10, start_ms=None, media=None)
        uc, _, _, _, _ = self._make_uc(candidate=candidate, source=None)

        with pytest.raises(InvalidTimecodesError):
            uc.execute_one(10)

    def test_execute_one_raises_invalid_timecodes_when_start_ms_none(self) -> None:
        media = CandidateMedia(
            candidate_id=10,
            screenshot_path=None,
            audio_path=None,
            start_ms=None,
            end_ms=2000,
            status=EnrichmentStatus.QUEUED,
            error=None,
            generated_at=None,
        )
        candidate = _make_candidate(10, media=media)
        uc, _, _, _, _ = self._make_uc(candidate=candidate, source=None)

        with pytest.raises(InvalidTimecodesError):
            uc.execute_one(10)

    def test_execute_one_raises_bad_video_format_when_source_missing(self) -> None:
        candidate = _make_candidate(10)
        source = MagicMock()
        source.id = 1
        source.video_path = None
        source.audio_track_index = 0

        uc, _, _, source_repo, _ = self._make_uc(candidate=candidate, source=source)

        with pytest.raises(BadVideoFormatError):
            uc.execute_one(10)

    def test_execute_one_raises_bad_video_format_when_file_missing(self, tmp_path: object) -> None:
        candidate = _make_candidate(10)
        source = _make_source("/nonexistent/path/movie.mp4")

        uc, _, _, _, _ = self._make_uc(candidate=candidate, source=source)

        exists_path = "backend.application.use_cases.run_media_extraction_job.os.path.exists"
        with patch(exists_path, return_value=False), pytest.raises(BadVideoFormatError):
            uc.execute_one(10)

    def test_execute_one_raises_permanent_when_source_not_found(self) -> None:
        """source_repo.get_by_id returns None → PermanentMediaError (line 62)."""
        candidate = _make_candidate(10)
        uc, _, _, source_repo, _ = self._make_uc(candidate=candidate, source=None)
        # source_repo already returns None by default from _make_uc

        with pytest.raises(PermanentMediaError, match="Source .* not found"):
            uc.execute_one(10)

    def test_execute_one_skips_upsert_when_cancelled_during_ffmpeg(self) -> None:
        """If the user cancels while ffmpeg runs, the row's status changes
        from RUNNING to FAILED. The use case must skip the upsert to avoid
        overwriting the user's cancellation (lines 87-91)."""
        candidate = _make_candidate(10)
        source = _make_source("/tmp/movie.mp4")

        uc, _, media_repo, _, _ = self._make_uc(candidate, source)
        # Pre-upsert check: status is FAILED (cancelled by user)
        media_repo.get_by_candidate_id.return_value = CandidateMedia(
            candidate_id=10,
            screenshot_path=None,
            audio_path=None,
            start_ms=1000,
            end_ms=2000,
            status=EnrichmentStatus.FAILED,
            error="cancelled by user",
            generated_at=None,
        )

        base = "backend.application.use_cases.run_media_extraction_job.os"
        with (
            patch(f"{base}.path.exists", return_value=True),
            patch(f"{base}.makedirs"),
        ):
            uc.execute_one(10)

        media_repo.upsert.assert_not_called()

    def test_execute_one_propagates_extractor_error(self) -> None:
        candidate = _make_candidate(10)
        source = _make_source("/tmp/movie.mp4")

        uc, _, _, _, media_extractor = self._make_uc(candidate=candidate, source=source)
        media_extractor.extract_screenshot.side_effect = OSError("ffmpeg crashed")

        base = "backend.application.use_cases.run_media_extraction_job.os"
        with (
            patch(f"{base}.path.exists", return_value=True),
            patch(f"{base}.makedirs"),
            pytest.raises(OSError, match="ffmpeg crashed"),
        ):
            uc.execute_one(10)
