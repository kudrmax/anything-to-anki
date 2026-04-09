from unittest.mock import MagicMock

import pytest
from backend.application.dto.video_dtos import TrackSelectionRequired, VideoSourceCreated
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.domain.value_objects.audio_track_info import AudioTrackInfo
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


def _make_audio_lister(tracks: list[AudioTrackInfo] | None = None) -> MagicMock:
    lister = MagicMock()
    lister.list_audio_tracks.return_value = tracks if tracks is not None else []
    return lister


@pytest.mark.unit
class TestCreateVideoSource:
    def test_external_srt_creates_source_directly(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        audio = _make_audio_lister([])
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(
            video_path="/tmp/movie.mp4",
            srt_text="1\n00:00:01,000 --> 00:00:02,000\nHello.\n",
            title="My Movie",
        )

        assert isinstance(result, VideoSourceCreated)
        extractor.list_tracks.assert_not_called()

    def test_single_embedded_track_auto_selected(self) -> None:
        track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        audio_track = AudioTrackInfo(index=0, language="eng", title=None, codec="aac", channels=2)
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([track])
        audio = _make_audio_lister([audio_track])
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, VideoSourceCreated)
        extractor.extract.assert_called_once_with("/tmp/movie.mp4", 0)

    def test_multiple_subtitle_tracks_returns_selection_required(self) -> None:
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor(tracks)
        audio = _make_audio_lister([])
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, TrackSelectionRequired)
        assert len(result.subtitle_tracks) == 2
        assert len(result.audio_tracks) == 0

    def test_multiple_audio_tracks_returns_selection_required(self) -> None:
        sub_track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        audio_tracks = [
            AudioTrackInfo(index=0, language="eng", title="English 5.1", codec="ac3", channels=6),
            AudioTrackInfo(index=1, language="rus", title="Russian", codec="aac", channels=2),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([sub_track])
        audio = _make_audio_lister(audio_tracks)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, TrackSelectionRequired)
        assert len(result.subtitle_tracks) == 0
        assert len(result.audio_tracks) == 2

    def test_both_ambiguous_returns_selection_required(self) -> None:
        sub_tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        audio_tracks = [
            AudioTrackInfo(index=0, language="eng", title=None, codec="ac3", channels=6),
            AudioTrackInfo(index=1, language="rus", title=None, codec="aac", channels=2),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor(sub_tracks)
        audio = _make_audio_lister(audio_tracks)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, TrackSelectionRequired)
        assert len(result.subtitle_tracks) == 2
        assert len(result.audio_tracks) == 2

    def test_subtitle_and_audio_selection_creates_source(self) -> None:
        sub_tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        audio_tracks = [
            AudioTrackInfo(index=0, language="eng", title=None, codec="ac3", channels=6),
            AudioTrackInfo(index=1, language="rus", title=None, codec="aac", channels=2),
        ]
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor(sub_tracks)
        audio = _make_audio_lister(audio_tracks)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(
            video_path="/tmp/movie.mp4",
            srt_text=None,
            title=None,
            subtitle_track_index=1,
            audio_track_index=1,
        )

        assert isinstance(result, VideoSourceCreated)
        extractor.extract.assert_called_once_with("/tmp/movie.mp4", 1)
        # Verify audio_track_index was passed to Source
        created_source = repo.create.call_args[0][0]
        assert created_source.audio_track_index == 1

    def test_no_tracks_and_no_srt_raises(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        audio = _make_audio_lister([])
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        with pytest.raises(ValueError, match="No subtitles"):
            uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

    def test_single_audio_track_sets_none_index(self) -> None:
        sub_track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        audio_track = AudioTrackInfo(index=0, language="eng", title=None, codec="aac", channels=2)
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([sub_track])
        audio = _make_audio_lister([audio_track])
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
        )

        result = uc.execute_video(video_path="/tmp/movie.mp4", srt_text=None, title=None)

        assert isinstance(result, VideoSourceCreated)
        created_source = repo.create.call_args[0][0]
        assert created_source.audio_track_index is None  # single track = ffmpeg default
