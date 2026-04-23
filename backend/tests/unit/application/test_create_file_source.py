from unittest.mock import MagicMock

import pytest
from backend.application.dto.video_dtos import TrackSelectionRequired, VideoSourceCreated
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


def _make_source_repo(source_id: int = 1) -> MagicMock:
    repo = MagicMock()
    created = MagicMock()
    created.id = source_id
    repo.create.return_value = created
    return repo


def _make_file_reader(content: str = "file content", exists: bool = True) -> MagicMock:
    reader = MagicMock()
    reader.exists.return_value = exists
    reader.read_text.return_value = content
    return reader


def _make_subtitle_extractor(tracks: list[SubtitleTrackInfo] | None = None) -> MagicMock:
    extractor = MagicMock()
    extractor.list_tracks.return_value = tracks or []
    extractor.extract.return_value = "1\n00:00:01,000 --> 00:00:02,000\nHello.\n"
    return extractor


def _make_audio_lister() -> MagicMock:
    lister = MagicMock()
    lister.list_audio_tracks.return_value = []
    return lister


@pytest.mark.unit
class TestExecuteFromFile:
    def test_text_file_reads_content_and_creates_source(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="hello", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="hello")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        result = uc.execute_from_file(file_path="/home/user/doc.txt")

        assert isinstance(result, Source)
        assert result.id == 1
        reader.read_text.assert_called_once_with("/home/user/doc.txt")

    def test_srt_file_creates_source_with_subtitles_input_method(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="srt content", status=SourceStatus.NEW,
            input_method=InputMethod.SUBTITLES_FILE, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        uc.execute_from_file(file_path="/home/user/subs.srt")

        created_source = repo.create.call_args[0][0]
        assert created_source.input_method == InputMethod.SUBTITLES_FILE

    def test_html_file_creates_text_source(self) -> None:
        repo = _make_source_repo()
        repo.create.return_value = Source(
            id=1, raw_text="<p>Hello</p>", status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        reader = _make_file_reader(content="<p>Hello</p>")
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        uc.execute_from_file(file_path="/home/user/article.html")

        created_source = repo.create.call_args[0][0]
        assert created_source.input_method == InputMethod.TEXT_PASTED

    def test_video_file_delegates_to_execute_video(self) -> None:
        repo = _make_source_repo()
        track = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        extractor = _make_subtitle_extractor([track])
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(file_path="/home/user/movie.mkv")

        assert isinstance(result, VideoSourceCreated)
        created_source = repo.create.call_args[0][0]
        assert created_source.video_path == "/home/user/movie.mkv"

    def test_video_with_srt_path_reads_srt(self) -> None:
        repo = _make_source_repo()
        extractor = _make_subtitle_extractor([])
        audio = _make_audio_lister()
        reader = _make_file_reader(content="1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(
            file_path="/home/user/movie.mp4",
            srt_path="/home/user/movie.srt",
        )

        assert isinstance(result, VideoSourceCreated)
        reader.read_text.assert_called_once_with("/home/user/movie.srt")

    def test_missing_file_raises_file_not_found(self) -> None:
        repo = _make_source_repo()
        reader = _make_file_reader(exists=False)
        uc = CreateSourceUseCase(source_repo=repo, file_reader=reader)

        with pytest.raises(FileNotFoundError, match="/nonexistent/file.txt"):
            uc.execute_from_file(file_path="/nonexistent/file.txt")

    def test_video_with_track_selection_required(self) -> None:
        repo = _make_source_repo()
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        extractor = _make_subtitle_extractor(tracks)
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(file_path="/home/user/movie.mov")

        assert isinstance(result, TrackSelectionRequired)

    def test_video_with_selected_tracks(self) -> None:
        repo = _make_source_repo()
        tracks = [
            SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip"),
            SubtitleTrackInfo(index=1, language="rus", title="Russian", codec="subrip"),
        ]
        extractor = _make_subtitle_extractor(tracks)
        audio = _make_audio_lister()
        reader = _make_file_reader(exists=True)
        uc = CreateSourceUseCase(
            source_repo=repo,
            subtitle_extractor=extractor,
            audio_track_lister=audio,
            file_reader=reader,
        )

        result = uc.execute_from_file(
            file_path="/home/user/movie.avi",
            subtitle_track_index=1,
            audio_track_index=0,
        )

        assert isinstance(result, VideoSourceCreated)
