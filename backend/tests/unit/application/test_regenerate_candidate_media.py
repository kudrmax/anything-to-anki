from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.application.use_cases.regenerate_candidate_media import (
    RegenerateCandidateMediaUseCase,
)
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.value_objects.parsed_srt import ParsedSrt
from backend.domain.value_objects.source_type import SourceType
from backend.domain.value_objects.subtitle_block import SubtitleBlock


def _make_parsed_srt() -> ParsedSrt:
    return ParsedSrt(
        text="Hello world. How are you?",
        blocks=(
            SubtitleBlock(start_ms=1000, end_ms=2000, char_start=0, char_end=12),
            SubtitleBlock(start_ms=3000, end_ms=4000, char_start=13, char_end=25),
        ),
    )


@pytest.mark.unit
class TestRegenerateCandidateMedia:
    def test_recomputes_timecodes_from_current_fragment(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.context_fragment = "How are you?"

        source = MagicMock()
        source.id = 42
        source.source_type = SourceType.VIDEO
        source.video_path = "/videos/movie.mkv"
        source.raw_text = "1\n00:00:01,000 --> 00:00:02,000\nHello world.\n\n2\n00:00:03,000 --> 00:00:04,000\nHow are you?\n"
        source.audio_track_index = None

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        parser = MagicMock()
        parser.parse_structured.return_value = _make_parsed_srt()
        media_extractor = MagicMock()
        media_repo = MagicMock()

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            source_repo=source_repo,
            structured_srt_parser=parser,
            media_extractor=media_extractor,
            media_root="/tmp/media",
        )

        with patch("backend.application.use_cases.regenerate_candidate_media.os.makedirs"), \
             patch("backend.application.use_cases.regenerate_candidate_media.os.path.exists", return_value=True):
            uc.execute(candidate_id=10)

        # Screenshot extracted at midpoint (3500 ms)
        screenshot_call = media_extractor.extract_screenshot.call_args
        assert screenshot_call.args[0] == "/videos/movie.mkv"
        assert screenshot_call.args[1] == 3500
        assert screenshot_call.args[2].endswith("10_screenshot.webp")

        # Audio extracted with new timecodes
        audio_call = media_extractor.extract_audio.call_args
        assert audio_call.args[0] == "/videos/movie.mkv"
        assert audio_call.args[1] == 3000
        assert audio_call.args[2] == 4000
        assert audio_call.args[3].endswith("10_audio.m4a")
        assert audio_call.kwargs.get("audio_track_index") is None

        # CandidateMedia upserted with correct fields
        media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = media_repo.upsert.call_args[0][0]
        assert upserted.candidate_id == 10
        assert upserted.start_ms == 3000
        assert upserted.end_ms == 4000
        assert upserted.screenshot_path.endswith("10_screenshot.webp")
        assert upserted.audio_path.endswith("10_audio.m4a")

    def test_uses_source_audio_track_index(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.context_fragment = "How are you?"

        source = MagicMock()
        source.id = 42
        source.source_type = SourceType.VIDEO
        source.video_path = "/videos/movie.mkv"
        source.raw_text = "irrelevant — parser is mocked"
        source.audio_track_index = 2

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        parser = MagicMock()
        parser.parse_structured.return_value = _make_parsed_srt()
        media_extractor = MagicMock()
        media_repo = MagicMock()

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            source_repo=source_repo,
            structured_srt_parser=parser,
            media_extractor=media_extractor,
            media_root="/tmp/media",
        )

        with patch("backend.application.use_cases.regenerate_candidate_media.os.makedirs"), \
             patch("backend.application.use_cases.regenerate_candidate_media.os.path.exists", return_value=True):
            uc.execute(candidate_id=10)

        audio_call = media_extractor.extract_audio.call_args
        assert audio_call.kwargs.get("audio_track_index") == 2

    def test_raises_if_candidate_not_found(self) -> None:
        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = None

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=MagicMock(),
            structured_srt_parser=MagicMock(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
        )

        with pytest.raises(ValueError, match="not found"):
            uc.execute(candidate_id=999)

    def test_raises_if_source_not_video(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        source = MagicMock()
        source.source_type = SourceType.TEXT

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            structured_srt_parser=MagicMock(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
        )

        with pytest.raises(ValueError, match="not a video"):
            uc.execute(candidate_id=10)

    def test_raises_if_video_file_missing(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        source = MagicMock()
        source.id = 42
        source.source_type = SourceType.VIDEO
        source.video_path = "/videos/missing.mkv"

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            structured_srt_parser=MagicMock(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
        )

        with patch("backend.application.use_cases.regenerate_candidate_media.os.path.exists", return_value=False):
            with pytest.raises(ValueError, match="Video file missing"):
                uc.execute(candidate_id=10)

    def test_raises_if_fragment_not_in_srt(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.context_fragment = "This text is not in SRT at all."

        source = MagicMock()
        source.id = 42
        source.source_type = SourceType.VIDEO
        source.video_path = "/videos/movie.mkv"
        source.raw_text = "irrelevant"
        source.audio_track_index = None

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        parser = MagicMock()
        parser.parse_structured.return_value = _make_parsed_srt()

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            structured_srt_parser=parser,
            media_extractor=MagicMock(),
            media_root="/tmp/media",
        )

        with patch("backend.application.use_cases.regenerate_candidate_media.os.path.exists", return_value=True):
            with pytest.raises(ValueError, match="Fragment not found"):
                uc.execute(candidate_id=10)
