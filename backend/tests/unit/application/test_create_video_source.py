import pytest
from unittest.mock import MagicMock
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.application.dto.video_dtos import VideoSourceCreated, SubtitleSelectionRequired
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


def _make_source_repo(source_id: int = 1) -> MagicMock:
    repo = MagicMock()
    created = MagicMock()
    created.id = source_id
    repo.create.return_value = created
    return repo


def _make_subtitle_extractor(tracks: list[SubtitleTrackInfo]) -> MagicMock:
    extractor = MagicMock()
    extractor.list_tracks.return_value = tracks
    extractor.extract.return_value = "1\n00:00:01,000 --> 00:00:02,000\nHello.\n"
    return extractor


@pytest.mark.unit
class TestCreateVideoSource:
    def test_external_srt_creates_source_directly(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        uc = CreateSourceUseCase(source_repo=repo, subtitle_extractor=extractor)

        result = uc.execute_video(
            video_path="/tmp/movie.mp4",
            srt_text="1\n00:00:01,000 --> 00:00:02,000\nHello.\n",
            title="My Movie",
        )

        assert isinstance(result, VideoSourceCreated)
        extractor.list_tracks.assert_not_called()

    def test_single_embedded_track_auto_selected(self) -> None:
        track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([track])
        uc = CreateSourceUseCase(source_repo=repo, subtitle_extractor=extractor)

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, VideoSourceCreated)
        extractor.extract.assert_called_once_with("/tmp/movie.mp4", 0)

    def test_multiple_tracks_returns_selection_required(self) -> None:
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor(tracks)
        uc = CreateSourceUseCase(source_repo=repo, subtitle_extractor=extractor)

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, SubtitleSelectionRequired)
        assert len(result.tracks) == 2

    def test_multiple_tracks_with_selection_creates_source(self) -> None:
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor(tracks)
        uc = CreateSourceUseCase(source_repo=repo, subtitle_extractor=extractor)

        result = uc.execute_video(
            video_path="/tmp/movie.mp4",
            srt_text=None,
            title=None,
            track_index=1,
        )

        assert isinstance(result, VideoSourceCreated)
        extractor.extract.assert_called_once_with("/tmp/movie.mp4", 1)

    def test_no_tracks_and_no_srt_raises(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        uc = CreateSourceUseCase(source_repo=repo, subtitle_extractor=extractor)

        with pytest.raises(ValueError, match="No subtitles"):
            uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)
