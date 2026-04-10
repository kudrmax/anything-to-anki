from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_source(input_method: InputMethod = InputMethod.YOUTUBE_URL) -> Source:
    return Source(
        raw_text="srt content",
        status=SourceStatus.DONE,
        input_method=input_method,
        content_type=ContentType.VIDEO,
        id=1,
        video_path="/tmp/test_video.mp4",
    )


def _make_media(status: EnrichmentStatus = EnrichmentStatus.DONE) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=10,
        screenshot_path="/tmp/s.webp",
        audio_path="/tmp/a.m4a",
        start_ms=0,
        end_ms=1000,
        status=status,
        error=None,
        generated_at=None,
    )


class TestCleanupYoutubeVideo:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.media_repo = MagicMock()
        self.use_case = CleanupYoutubeVideoUseCase(
            source_repo=self.source_repo,
            media_repo=self.media_repo,
        )

    def test_deletes_video_when_all_media_done(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_path = f.name
        source = _make_source()
        source.video_path = tmp_path
        self.source_repo.get_by_id.return_value = source
        self.media_repo.get_all_by_source_id.return_value = [
            _make_media(EnrichmentStatus.DONE),
            _make_media(EnrichmentStatus.DONE),
        ]
        self.use_case.execute(1)
        assert not os.path.exists(tmp_path)
        self.source_repo.update_video_path.assert_called_once_with(1, None)

    def test_skips_if_not_youtube(self) -> None:
        source = _make_source(InputMethod.VIDEO_FILE)
        self.source_repo.get_by_id.return_value = source
        self.media_repo.get_all_by_source_id.return_value = [_make_media()]
        self.use_case.execute(1)
        self.source_repo.update_video_path.assert_not_called()

    def test_skips_if_media_not_all_done(self) -> None:
        source = _make_source()
        self.source_repo.get_by_id.return_value = source
        self.media_repo.get_all_by_source_id.return_value = [
            _make_media(EnrichmentStatus.DONE),
            _make_media(EnrichmentStatus.RUNNING),
        ]
        self.use_case.execute(1)
        self.source_repo.update_video_path.assert_not_called()

    def test_skips_if_no_video_path(self) -> None:
        source = _make_source()
        source.video_path = None
        self.source_repo.get_by_id.return_value = source
        self.use_case.execute(1)
        self.source_repo.update_video_path.assert_not_called()
